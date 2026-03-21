// HomeDomainClient.cpp
#define WIN32_LEAN_AND_MEAN
#define SERVICE_NAME        L"RMMAgent"
#define REG_BASE_PATH       L"SOFTWARE\\MYRMM\\Secrets"
#define LOG_FILE_NAME       L"agent.log"


#include <windows.h>
#include <winhttp.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <winioctl.h>
#include <tlhelp32.h>
#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <filesystem>
#include <sstream>
#include <objbase.h>
#include <iomanip>
#include <wincrypt.h>
#include <sddl.h>
#include <string>
#include <iphlpapi.h>
#include "json.hpp"
#include <iomanip>
#include <chrono>
#include <psapi.h>
#include <ctime>
#include <thread>
#include <atomic>

std::wstring GetExecutableDir() {
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(NULL, path, MAX_PATH);
    return std::filesystem::path(path).parent_path().wstring();
}


#pragma comment(lib, "winhttp.lib")
#pragma comment(lib, "Ws2_32.lib")
#pragma comment(lib, "Ole32.lib")
#pragma comment(lib, "Iphlpapi.lib")
#pragma comment(lib, "pdh.lib")

std::wstring g_baseDir;



using json = nlohmann::json;

bool logging_enabled = true;

int install_service();

static std::atomic<bool> g_stopRequested{ false };
static HANDLE g_stopEvent = nullptr;
static std::ofstream g_log;

struct AgentConf {
    std::string agent_id;
    std::string agent_auth;
    std::string server;            
    std::string expected_server_auth;
};

struct LocalTask {
    std::string task_id;
    std::string cmd;
    std::string shell;
    std::string file_url;
    std::string save_path;
    int timeout_seconds;
    std::string task_type;
    std::string status;  // RUNNING, DONE, FAILED
    std::string received_at;  // Время получения
    std::string deadline;     // Время до которого задача должна быть выполнена
    int retry_count;
};

std::wstring GetTasksFilePath() {
    return g_baseDir + L"\\tasks.json";
}

std::string agent_auth_from_file = "";  // загрузка из agent.conf
std::string server_auth_from_file = ""; // загрузка из agent.conf

std::string agent_auth;
std::string server_auth;


static std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \r\n\t");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \r\n\t");
    return s.substr(a, b - a + 1);
}

bool http_get_string(const std::string& server_url, const std::string& path, std::string& out);
bool download_file(const std::string& url, const std::string& save_path, bool overwrite);
std::string sha256_file(const std::string& path);
std::string json_unescape(const std::string& s);
bool server_alive(const std::string& url);

namespace fs = std::filesystem;


static std::string extract_json_string(const std::string& json, const std::string& key) {
    std::string patt = "\"" + key + "\"";
    size_t pos = json.find(patt);
    if (pos == std::string::npos) return "";
    pos = json.find(':', pos);
    if (pos == std::string::npos) return "";
    size_t q1 = json.find('"', pos);
    if (q1 == std::string::npos) return "";
    size_t q2 = json.find('"', q1 + 1);
    if (q2 == std::string::npos) return "";
    return json.substr(q1 + 1, q2 - q1 - 1);
}


// Сохранить задачи в файл
void SaveLocalTasks(const std::vector<LocalTask>& tasks) {
    try {
        json j_arr = json::array();
        for (const auto& task : tasks) {
            json j_task;
            j_task["task_id"] = task.task_id;
            j_task["cmd"] = task.cmd;
            j_task["shell"] = task.shell;
            j_task["file_url"] = task.file_url;
            j_task["save_path"] = task.save_path;
            j_task["timeout_seconds"] = task.timeout_seconds;
            j_task["task_type"] = task.task_type;
            j_task["status"] = task.status;
            j_task["received_at"] = task.received_at;
            j_task["deadline"] = task.deadline;
            j_task["retry_count"] = task.retry_count;
            j_arr.push_back(j_task);
        }

        std::ofstream file(GetTasksFilePath());
        if (file.is_open()) {
            file << j_arr.dump(2);
            file.close();
        }
    }
    catch (const std::exception& e) {
        std::cerr << "[ERROR] SaveLocalTasks failed: " << e.what() << std::endl;
    }
}

// Загрузить задачи из файла
std::vector<LocalTask> LoadLocalTasks() {
    std::vector<LocalTask> tasks;
    try {
        std::ifstream file(GetTasksFilePath());
        if (!file.is_open()) {
            return tasks;  // Файл не существует
        }

        std::string content((std::istreambuf_iterator<char>(file)),
            std::istreambuf_iterator<char>());
        file.close();

        if (content.empty()) {
            return tasks;
        }

        json j_arr = json::parse(content);
        for (const auto& j_task : j_arr) {
            LocalTask task;
            task.task_id = j_task.value("task_id", "");
            task.cmd = j_task.value("cmd", "");
            task.shell = j_task.value("shell", "cmd");
            task.file_url = j_task.value("file_url", "");
            task.save_path = j_task.value("save_path", "");
            task.timeout_seconds = j_task.value("timeout_seconds", 300);
            task.task_type = j_task.value("task_type", "RUN_CMD");
            task.status = j_task.value("status", "PENDING");
            task.received_at = j_task.value("received_at", "");
            task.deadline = j_task.value("deadline", "");
            task.retry_count = j_task.value("retry_count", 0);
            tasks.push_back(task);
        }
    }
    catch (const std::exception& e) {
        std::cerr << "[ERROR] LoadLocalTasks failed: " << e.what() << std::endl;
    }
    return tasks;
}

// Проверить истекло ли время задачи
bool IsTaskExpired(const LocalTask& task) {
    try {
        // Парсим deadline
        std::tm tm_deadline = {};
        std::istringstream ss(task.deadline);
        ss >> std::get_time(&tm_deadline, "%Y-%m-%dT%H:%M:%S");

        if (ss.fail()) {
            return false;
        }

        std::time_t deadline_time = std::mktime(&tm_deadline);
        std::time_t current_time = std::time(nullptr);

        return current_time > deadline_time;
    }
    catch (...) {
        return false;
    }
}

// Вычислить deadline для задачи
std::string CalculateDeadline(int timeout_seconds) {
    auto now = std::chrono::system_clock::now();
    auto deadline = now + std::chrono::seconds(timeout_seconds);
    std::time_t deadline_time = std::chrono::system_clock::to_time_t(deadline);

    std::tm tm_deadline;
    gmtime_s(&tm_deadline, &deadline_time);

    std::ostringstream oss;
    oss << std::put_time(&tm_deadline, "%Y-%m-%dT%H:%M:%SZ");
    return oss.str();
}



int uninstall_service() {
    SC_HANDLE scm = OpenSCManager(nullptr, nullptr, SC_MANAGER_ALL_ACCESS);
    if (!scm) return 1;

    SC_HANDLE svc = OpenServiceW(scm, SERVICE_NAME, DELETE | SERVICE_STOP);
    if (svc) {
        SERVICE_STATUS ss;
        // Пытаемся остановить службу перед удалением
        ControlService(svc, SERVICE_CONTROL_STOP, &ss);
        // Удаляем из системы
        if (DeleteService(svc)) {
            // Опционально: удаляем ключи из реестра, если создавали их
            RegDeleteTreeW(HKEY_LOCAL_MACHINE, REG_BASE_PATH);
        }
        CloseServiceHandle(svc);
    }

    CloseServiceHandle(scm);
    return 0;
}

// get broadcast addresses for IPv4 per adapter (skips tunnel/loopback)
static std::vector<std::string> get_ipv4_broadcast_addresses() {
    std::vector<std::string> outs;

    ULONG flags = GAA_FLAG_INCLUDE_PREFIX;
    ULONG family = AF_INET;
    ULONG outBufLen = 15000;
    PIP_ADAPTER_ADDRESSES pAddresses = (PIP_ADAPTER_ADDRESSES)malloc(outBufLen);
    if (!pAddresses) return outs;

    ULONG rv = GetAdaptersAddresses(family, flags, NULL, pAddresses, &outBufLen);
    if (rv == ERROR_BUFFER_OVERFLOW) {
        free(pAddresses);
        pAddresses = (PIP_ADAPTER_ADDRESSES)malloc(outBufLen);
        rv = GetAdaptersAddresses(family, flags, NULL, pAddresses, &outBufLen);
    }
    if (rv != NO_ERROR) {
        if (pAddresses) free(pAddresses);
        return outs;
    }

    for (PIP_ADAPTER_ADDRESSES pCurr = pAddresses; pCurr != NULL; pCurr = pCurr->Next) {
        // skip down adapters
        if (pCurr->OperStatus != IfOperStatusUp) continue;
        // prefer real NICs: Ethernet or WiFi; skip tunnels and loopback
        // IF_TYPE: IF_TYPE_ETHERNET_CSMACD (6), IF_TYPE_IEEE80211 (71)
        if (!(pCurr->IfType == IF_TYPE_ETHERNET_CSMACD || pCurr->IfType == IF_TYPE_IEEE80211)) {
            // allow but deprioritize later, so continue to include but mark?
            // For simplicity, skip other types to avoid VPN/tunnel unless no other answers come.
            continue;
        }

        // For each unicast address on the adapter
        for (PIP_ADAPTER_UNICAST_ADDRESS ua = pCurr->FirstUnicastAddress; ua != NULL; ua = ua->Next) {
            SOCKADDR* sa = ua->Address.lpSockaddr;
            if (!sa) continue;
            if (sa->sa_family != AF_INET) continue;
            sockaddr_in* sin = (sockaddr_in*)sa;
            uint32_t ip = ntohl(sin->sin_addr.s_addr);
            // find prefix length from adapter prefixes: match by address
            // fallback: use first prefix in adapter if present
            UINT32 prefixLen = 24; // fallback
            for (PIP_ADAPTER_PREFIX pref = pCurr->FirstPrefix; pref; pref = pref->Next) {
                // pref->Address may be IPv4
                if (pref->Address.lpSockaddr && pref->Address.lpSockaddr->sa_family == AF_INET) {
                    prefixLen = pref->PrefixLength;
                    break;
                }
            }
            if (prefixLen > 32) prefixLen = 32;
            uint32_t mask = prefixLen == 0 ? 0 : (prefixLen == 32 ? 0xFFFFFFFFu : (~0u << (32 - prefixLen)));
            uint32_t bcast = (ip & mask) | (~mask);
            in_addr a; a.S_un.S_addr = htonl(bcast);
            char buf[64]; inet_ntop(AF_INET, &a, buf, sizeof(buf));
            outs.emplace_back(std::string(buf));
        }
    }

    free(pAddresses);
    // Remove duplicates
    sort(outs.begin(), outs.end());
    outs.erase(std::unique(outs.begin(), outs.end()), outs.end());
    return outs;
}

// Добавьте эту функцию после log_init
void rotate_log_if_needed(const std::wstring& log_path, size_t max_size_mb = 8) {
    try {
        // Проверяем размер файла
        std::filesystem::path p(log_path);
        if (std::filesystem::exists(p)) {
            auto file_size = std::filesystem::file_size(p);
            size_t max_size_bytes = max_size_mb * 1024 * 1024;

            if (file_size > max_size_bytes) {
                // Открываем файл для чтения
                std::ifstream in(log_path, std::ios::binary);
                if (!in) return;

                // Читаем весь файл
                std::vector<std::string> lines;
                std::string line;
                while (std::getline(in, line)) {
                    lines.push_back(line);
                }
                in.close();

                // Если файл очень большой, сохраняем только последние ~50% строк
                size_t keep_lines = lines.size() / 2; // Сохраняем половину
                if (keep_lines < 100) keep_lines = 100; // Но не менее 100 строк

                // Открываем файл для записи (это очистит его)
                std::ofstream out(log_path, std::ios::binary | std::ios::trunc);
                if (!out) return;

                // Записываем только последние строки
                for (size_t i = lines.size() - keep_lines; i < lines.size(); ++i) {
                    out << lines[i] << "\n";
                }

                out.close();

                // Логируем факт ротации
                auto now = std::time(nullptr);
                std::tm tmNow;
                localtime_s(&tmNow, &now);

                std::ofstream log_append(log_path, std::ios::app);
                if (log_append) {
                    log_append << "[" << std::put_time(&tmNow, "%F %T") << "] "
                        << "LOG ROTATED: File size exceeded " << max_size_mb
                        << " MB, truncated to " << keep_lines << " lines\n";
                }
            }
        }
    }
    catch (const std::exception& e) {
        // В случае ошибки просто игнорируем
    }
    catch (...) {
        // Игнорируем любые исключения
    }
}

void log_init(const std::wstring& baseDir, bool enabled) {
    if (!enabled) return;

    std::filesystem::path p(baseDir);
    p /= LOG_FILE_NAME;

    // Проверяем и ротируем лог перед открытием
    rotate_log_if_needed(p.wstring(), 8);

    g_log.open(p, std::ios::app);

    if (g_log) {
        auto now = std::time(nullptr);
        char timeBuf[26];
        ctime_s(timeBuf, sizeof(timeBuf), &now);
        g_log << "==== Agent start: " << timeBuf;
        g_log.flush();
    }
}

void log_line(const std::string& s) {
    if (!g_log) return;

    auto now = std::time(nullptr);
    std::tm tmNow;
    localtime_s(&tmNow, &now);
    g_log << "[" << std::put_time(&tmNow, "%F %T") << "] "
        << s << "\n";
    g_log.flush();

    // Периодическая проверка размера (каждые 100 записей)
    static int log_counter = 0;
    if (++log_counter >= 100) {
        log_counter = 0;
        std::filesystem::path p(g_baseDir);
        p /= LOG_FILE_NAME;
        rotate_log_if_needed(p.wstring(), 8);
    }
}

bool read_secret_from_registry(const std::wstring& valueName, std::vector<BYTE>& out) {
    HKEY hKey = nullptr;
    if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, REG_BASE_PATH, 0, KEY_READ, &hKey) != ERROR_SUCCESS)
        return false;

    DWORD type = 0;
    DWORD size = 0;
    if (RegQueryValueExW(hKey, valueName.c_str(), nullptr, &type, nullptr, &size) != ERROR_SUCCESS ||
        type != REG_BINARY || size == 0) {
        RegCloseKey(hKey);
        return false;
    }

    out.resize(size);
    bool ok = (RegQueryValueExW(hKey, valueName.c_str(), nullptr, nullptr,
        out.data(), &size) == ERROR_SUCCESS);

    RegCloseKey(hKey);
    return ok;
}

std::string load_secret(const std::wstring& regName,
    const std::string& fileValue) {
    std::vector<BYTE> data;
    if (read_secret_from_registry(regName, data)) {
        return std::string((char*)data.data(), data.size());
    }
    return fileValue; // fallback к agent.conf
}



bool is_vpn_adapter(PIP_ADAPTER_ADDRESSES adapter) {
    // 1. Проверка по типу (пропускаем виртуальные и туннели)
    if (adapter->IfType == IF_TYPE_PROP_VIRTUAL || adapter->IfType == IF_TYPE_TUNNEL)
        return true;

    // 2. Проверка по описанию (ищем ключевые слова VPN)
    std::wstring description = adapter->Description;
    if (description.find(L"TAP") != std::wstring::npos ||
        description.find(L"VPN") != std::wstring::npos ||
        description.find(L"Virtual") != std::wstring::npos) {
        return true;
    }
    return false;
}

std::string discover_server_smart(int config_port, int timeout_ms = 3000) {
    const int DEFAULT_UDP_PORT = 37020;
    const char* discovery_msg = "CLIENT_QUERY_2026";

    std::vector<std::string> broadcast_ips;

    // Получаем список всех адаптеров
    ULONG outBufLen = 15000;
    PIP_ADAPTER_ADDRESSES pAddresses = (IP_ADAPTER_ADDRESSES*)malloc(outBufLen);
    if (GetAdaptersAddresses(AF_INET, GAA_FLAG_INCLUDE_PREFIX, NULL, pAddresses, &outBufLen) == NO_ERROR) {
        for (PIP_ADAPTER_ADDRESSES pCurr = pAddresses; pCurr != NULL; pCurr = pCurr->Next) {
            // ВАЖНО: Пропускаем VPN и неактивные интерфейсы
            if (pCurr->OperStatus != IfOperStatusUp || is_vpn_adapter(pCurr)) continue;

            for (PIP_ADAPTER_UNICAST_ADDRESS ua = pCurr->FirstUnicastAddress; ua != NULL; ua = ua->Next) {
                sockaddr_in* sin = (sockaddr_in*)ua->Address.lpSockaddr;
                uint32_t ip = ntohl(sin->sin_addr.s_addr);

                // Вычисляем Broadcast адрес для этого интерфейса (упрощенно /24)
                // В идеале берем PrefixLength, но 255.255.255.255 тоже сработает локально
                uint32_t bcast = ip | 0x000000FF;
                in_addr a; a.S_un.S_addr = htonl(bcast);
                char buf[64]; inet_ntop(AF_INET, &a, buf, sizeof(buf));
                broadcast_ips.push_back(buf);
            }
        }
    }
    if (pAddresses) free(pAddresses);
    broadcast_ips.push_back("255.255.255.255"); // Глобальный широковещательный

    SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    char bVal = 1;
    setsockopt(sock, SOL_SOCKET, SO_BROADCAST, &bVal, sizeof(bVal));
    int tv = timeout_ms;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&tv, sizeof(tv));

    for (auto& bcast_ip : broadcast_ips) {
        sockaddr_in to;
        to.sin_family = AF_INET;
        to.sin_port = htons(DEFAULT_UDP_PORT);
        inet_pton(AF_INET, bcast_ip.c_str(), &to.sin_addr);
        sendto(sock, discovery_msg, (int)strlen(discovery_msg), 0, (sockaddr*)&to, sizeof(to));
    }

    char buf[1024];
    sockaddr_in from; int fromlen = sizeof(from);
    int ret = recvfrom(sock, buf, sizeof(buf) - 1, 0, (sockaddr*)&from, &fromlen);

    if (ret > 0) {
        buf[ret] = 0;
        auto resp = json::parse(buf);
        std::string url = resp["url"]; // Например "http://192.168.1.10:5000"

        // ВАЖНО: Проверка порта из конфига
        if (config_port > 0) {
            size_t colon = url.find_last_of(':');
            if (colon != std::string::npos) {
                int server_port = std::stoi(url.substr(colon + 1));
                if (server_port != config_port) {
                    closesocket(sock);
                    return ""; // Порт не совпадает, игнорируем сервер
                }
            }
        }
        closesocket(sock);
        return url;
    }
    closesocket(sock);
    return "";
}

std::string sha256_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return "";
    HCRYPTPROV hProv = 0;
    HCRYPTHASH hHash = 0;
    if (!CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) return "";
    if (!CryptCreateHash(hProv, CALG_SHA_256, 0, 0, &hHash)) { CryptReleaseContext(hProv, 0); return ""; }
    char buf[8192];
    while (f.read(buf, sizeof(buf))) {
        CryptHashData(hHash, (BYTE*)buf, (DWORD)f.gcount(), 0);
    }
    CryptHashData(hHash, (BYTE*)buf, (DWORD)f.gcount(), 0);
    BYTE hash[32];
    DWORD len = 32;
    CryptGetHashParam(hHash, HP_HASHVAL, hash, &len, 0);
    std::ostringstream oss;
    for (DWORD i = 0; i < len; i++) oss << std::hex << std::setw(2) << std::setfill('0') << (int)hash[i];
    CryptDestroyHash(hHash); CryptReleaseContext(hProv, 0);
    return oss.str();
}

bool http_get_string(const std::string& server_url, const std::string& path, std::string& out) {
    // unchanged code from original — but careful: server returns envelope JSON including server_auth and hmac
    std::string proto, hostport;
    if (server_url.rfind("http://", 0) == 0) {
        proto = "http";
        hostport = server_url.substr(7);
    }
    else if (server_url.rfind("https://", 0) == 0) {
        proto = "https";
        hostport = server_url.substr(8);
    }
    else return false;


    HINTERNET hSession = WinHttpOpen(L"Agent/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, NULL, NULL, 0);
    if (!hSession) return false;

    // КРИТИЧЕСКИЙ БЛОК: Включаем TLS 1.2 на Windows 7
    DWORD dwProtocols = WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_2;
    WinHttpSetOption(hSession, WINHTTP_OPTION_SECURE_PROTOCOLS, &dwProtocols, sizeof(dwProtocols));

    std::string host = hostport;
    INTERNET_PORT port = (proto == "https") ? INTERNET_DEFAULT_HTTPS_PORT : INTERNET_DEFAULT_HTTP_PORT;
    size_t pos = hostport.find(':');
    if (pos != std::string::npos) {
        host = hostport.substr(0, pos);
        port = (INTERNET_PORT)std::stoi(hostport.substr(pos + 1));
    }

    // HINTERNET hSession = WinHttpOpen(L"Agent/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hSession) return false;

    std::wstring whost(host.begin(), host.end());
    HINTERNET hConnect = WinHttpConnect(hSession, whost.c_str(), port, 0);
    if (!hConnect) { WinHttpCloseHandle(hSession); return false; }

    std::wstring wpath(path.begin(), path.end());
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"GET", wpath.c_str(), NULL, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, (proto == "https") ? WINHTTP_FLAG_SECURE : 0);
    bool result = false;
    if (hRequest) {
        if (proto == "https") {
            DWORD dwFlags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                SECURITY_FLAG_IGNORE_CERT_CN_INVALID |
                SECURITY_FLAG_IGNORE_CERT_DATE_INVALID;
            WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &dwFlags, sizeof(dwFlags));
        }
        if (WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0)) {
            if (WinHttpReceiveResponse(hRequest, NULL)) {
                DWORD dwSize = 0;
                out.clear();
                while (WinHttpQueryDataAvailable(hRequest, &dwSize) && dwSize > 0) {
                    std::vector<char> buffer(dwSize);
                    DWORD downloaded = 0;
                    if (WinHttpReadData(hRequest, buffer.data(), dwSize, &downloaded)) {
                        out.append(buffer.data(), downloaded);
                    }
                    else break;
                }
                result = true;
            }
        }
        WinHttpCloseHandle(hRequest);
    }
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hSession);
    return result;
}

std::string get_system_agent_id() {
    char computerName[MAX_COMPUTERNAME_LENGTH + 1];
    DWORD size = sizeof(computerName);
    if (!GetComputerNameA(computerName, &size)) return "0000000000";

    BYTE sid[SECURITY_MAX_SID_SIZE];
    DWORD sidSize = sizeof(sid);
    char domainName[MAX_PATH];
    DWORD domainNameSize = sizeof(domainName);
    SID_NAME_USE snu;

    // Попытка получить SID компьютера
    if (LookupAccountNameA(NULL, computerName, sid, &sidSize, domainName, &domainNameSize, &snu)) {
        PSID pSid = (PSID)sid;
        if (IsValidSid(pSid)) {
            PUCHAR subAuthCount = GetSidSubAuthorityCount(pSid);
            if (subAuthCount && *subAuthCount > 0) {
                DWORD lastIdx = (DWORD)(*subAuthCount) - 1;
                PDWORD lastSubAuth = GetSidSubAuthority(pSid, lastIdx);
                if (lastSubAuth) {
                    return std::to_string(*lastSubAuth);
                }
            }
        }
    }

    // Если не удалось достать SID — запасной идентификатор на основе 64-bit tickcount
    ULONGLONG ticks = GetTickCount64();
    return "ID-" + std::to_string(ticks);
}

bool download_file(const std::string& url, const std::string& save_path, bool overwrite) {
    HINTERNET hSession = NULL, hConnect = NULL, hRequest = NULL;
    std::ofstream ofs;

    try {
        fs::path out(save_path);

        std::cout << "[DEBUG] Скачивание файла: " << url << std::endl;
        std::cout << "[DEBUG] Сохраняем в: " << save_path << std::endl;

        // 1. Создаем папки, если их нет
        if (out.has_parent_path()) {
            fs::create_directories(out.parent_path());
        }

        // 2. Проверка перезаписи
        if (fs::exists(out) && fs::is_regular_file(out) && !overwrite) {
            std::cout << "[!] File exists, skipping: " << out.string() << "\n";
            return true;
        }

        // 3. Парсинг URL
        std::string proto, hostport;
        if (url.rfind("http://", 0) == 0) {
            proto = "http"; hostport = url.substr(7);
        }
        else if (url.rfind("https://", 0) == 0) {
            proto = "https"; hostport = url.substr(8);
        }
        else {
            return false;
        }

        size_t slash = hostport.find('/');
        std::string host = (slash == std::string::npos) ? hostport : hostport.substr(0, slash);
        std::string path = (slash == std::string::npos) ? "/" : hostport.substr(slash);

        INTERNET_PORT port = (proto == "https") ? INTERNET_DEFAULT_HTTPS_PORT : INTERNET_DEFAULT_HTTP_PORT;
        size_t colon = host.find(':');
        if (colon != std::string::npos) {
            port = (INTERNET_PORT)std::stoi(host.substr(colon + 1));
            host = host.substr(0, colon);
        }

        // 4. WinHTTP Инициализация
        hSession = WinHttpOpen(L"AgentDownload/1.1", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, NULL, NULL, 0);
        if (!hSession) return false;

        std::wstring whost(host.begin(), host.end());
        hConnect = WinHttpConnect(hSession, whost.c_str(), port, 0);
        if (!hConnect) goto cleanup;

        std::wstring wpath(path.begin(), path.end());
        hRequest = WinHttpOpenRequest(hConnect, L"GET", wpath.c_str(), NULL, WINHTTP_NO_REFERER,
            WINHTTP_DEFAULT_ACCEPT_TYPES, (proto == "https" ? WINHTTP_FLAG_SECURE : 0));
        if (!hRequest) goto cleanup;
        if (proto == "https") {
            DWORD dwFlags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                SECURITY_FLAG_IGNORE_CERT_CN_INVALID |
                SECURITY_FLAG_IGNORE_CERT_DATE_INVALID;
            WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &dwFlags, sizeof(dwFlags));
        }

        // 5. Запрос
        if (!WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0, NULL, 0, 0, 0)) goto cleanup;
        if (!WinHttpReceiveResponse(hRequest, NULL)) goto cleanup;

        // --- КРИТИЧЕСКАЯ ПРОВЕРКА: Статус код должен быть 200 ---
        DWORD dwStatusCode = 0;
        DWORD dwSize = sizeof(dwStatusCode);
        WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
            NULL, &dwStatusCode, &dwSize, NULL);

        if (dwStatusCode != 200) {
            std::cerr << "[!] Server returned HTTP Error: " << dwStatusCode << "\n";
            goto cleanup;
        }

        // 6. Запись файла в бинарном режиме
        ofs.open(out, std::ios::binary | std::ios::out | std::ios::trunc);
        if (!ofs.is_open()) goto cleanup;

        DWORD avail = 0;
        while (WinHttpQueryDataAvailable(hRequest, &avail) && avail > 0) {
            std::vector<char> buf(avail);
            DWORD read = 0;
            if (!WinHttpReadData(hRequest, buf.data(), avail, &read)) break;
            ofs.write(buf.data(), read);
        }
        ofs.close();

        // Успешное завершение
        WinHttpCloseHandle(hRequest); WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession);
        std::cout << "[+] Successfully saved: " << out.string() << "\n";
        return true;

    }
    catch (...) {
        std::cerr << "[!] Exception in download_file\n";
    }

cleanup:
    if (hRequest) WinHttpCloseHandle(hRequest);
    if (hConnect) WinHttpCloseHandle(hConnect);
    if (hSession) WinHttpCloseHandle(hSession);
    if (ofs.is_open()) ofs.close();
    return false;
}

bool http_post_raw(const std::string& server_url, const std::string& path, const std::vector<char>& data, std::string* out_body = nullptr) {
    std::string proto, hostport;
    if (server_url.rfind("http://", 0) == 0) {
        proto = "http"; hostport = server_url.substr(7);
    }
    else if (server_url.rfind("https://", 0) == 0) {
        proto = "https"; hostport = server_url.substr(8);
    }
    else return false;

    std::string host = hostport;
    INTERNET_PORT port = (proto == "https") ? INTERNET_DEFAULT_HTTPS_PORT : INTERNET_DEFAULT_HTTP_PORT;
    size_t pos = hostport.find(':');
    if (pos != std::string::npos) {
        host = hostport.substr(0, pos);
        port = (INTERNET_PORT)std::stoi(hostport.substr(pos + 1));
    }

    HINTERNET hSession = WinHttpOpen(L"AgentUpload/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hSession) {
        std::cout << "[ERROR] WinHttpOpen failed" << std::endl;
        return false;
    }

    std::wstring whost(host.begin(), host.end());
    HINTERNET hConnect = WinHttpConnect(hSession, whost.c_str(), port, 0);
    if (!hConnect) {
        std::cout << "[ERROR] WinHttpConnect failed for " << host << ":" << port << std::endl;
        WinHttpCloseHandle(hSession);
        return false;
    }

    std::wstring wpath(path.begin(), path.end());
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"POST", wpath.c_str(), NULL,
        WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES,
        (proto == "https") ? WINHTTP_FLAG_SECURE : 0);
    if (!hRequest) {
        std::cout << "[ERROR] WinHttpOpenRequest failed for path: " << path << std::endl;
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        return false;
    }

    if (proto == "https") {
        DWORD dwFlags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
            SECURITY_FLAG_IGNORE_CERT_CN_INVALID |
            SECURITY_FLAG_IGNORE_CERT_DATE_INVALID;
        WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &dwFlags, sizeof(dwFlags));
    }

    // Добавляем заголовок Content-Type
    std::string headers = "Content-Type: application/octet-stream\r\n";
    std::wstring wheaders(headers.begin(), headers.end());

    std::cout << "[DEBUG] Отправка POST запроса на " << path << ", размер данных: " << data.size() << " байт" << std::endl;

    BOOL bSend = WinHttpSendRequest(hRequest, wheaders.c_str(), -1L,
        (LPVOID)data.data(), (DWORD)data.size(),
        (DWORD)data.size(), 0);
    if (!bSend) {
        DWORD error = GetLastError();
        std::cout << "[ERROR] WinHttpSendRequest failed, error: " << error << std::endl;
        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        return false;
    }

    if (!WinHttpReceiveResponse(hRequest, NULL)) {
        std::cout << "[ERROR] WinHttpReceiveResponse failed" << std::endl;
        WinHttpCloseHandle(hRequest);
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hSession);
        return false;
    }

    // Получаем статус код
    DWORD dwStatusCode = 0;
    DWORD dwSize = sizeof(dwStatusCode);
    WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
        NULL, &dwStatusCode, &dwSize, NULL);

    std::cout << "[DEBUG] HTTP статус ответа: " << dwStatusCode << std::endl;

    if (out_body) {
        DWORD dwReadSize = 0;
        out_body->clear();
        while (WinHttpQueryDataAvailable(hRequest, &dwReadSize) && dwReadSize > 0) {
            std::vector<char> buffer(dwReadSize);
            DWORD downloaded = 0;
            if (!WinHttpReadData(hRequest, buffer.data(), dwReadSize, &downloaded)) {
                std::cout << "[ERROR] WinHttpReadData failed" << std::endl;
                break;
            }
            out_body->append(buffer.data(), downloaded);
        }
        std::cout << "[DEBUG] Получено ответа: " << out_body->size() << " байт" << std::endl;
    }

    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hSession);

    return (dwStatusCode >= 200 && dwStatusCode < 300);
}

bool http_post_json(const std::string& server_url, const std::string& path, const std::string& json_body, std::string* out_body = nullptr) {
    std::string proto, hostport;
    if (server_url.rfind("http://", 0) == 0) { proto = "http"; hostport = server_url.substr(7); }
    else if (server_url.rfind("https://", 0) == 0) { proto = "https"; hostport = server_url.substr(8); }
    else return false;
    std::string host = hostport; INTERNET_PORT port = (proto == "https") ? INTERNET_DEFAULT_HTTPS_PORT : INTERNET_DEFAULT_HTTP_PORT;
    size_t pos = hostport.find(':');
    if (pos != std::string::npos) { host = hostport.substr(0, pos); port = (INTERNET_PORT)std::stoi(hostport.substr(pos + 1)); }
    HINTERNET hSession = WinHttpOpen(L"TelemetryAgent/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);  
    if (!hSession) return false;
    std::wstring whost(host.begin(), host.end());
    HINTERNET hConnect = WinHttpConnect(hSession, whost.c_str(), port, 0);
    if (!hConnect) { WinHttpCloseHandle(hSession); return false; }
    std::wstring wpath(path.begin(), path.end());
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"POST", wpath.c_str(), NULL, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, (proto == "https" ? WINHTTP_FLAG_SECURE : 0));
    if (!hRequest) { WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession); return false; }
    if (proto == "https") {
        DWORD dwFlags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
            SECURITY_FLAG_IGNORE_CERT_CN_INVALID |
            SECURITY_FLAG_IGNORE_CERT_DATE_INVALID;
        WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &dwFlags, sizeof(dwFlags));
    }
    std::string headers = "Content-Type: application/json\r\n";
    std::wstring wheaders(headers.begin(), headers.end());
    BOOL sent = WinHttpSendRequest(hRequest, wheaders.c_str(), (DWORD)-1L, (LPVOID)json_body.c_str(), (DWORD)json_body.size(), (DWORD)json_body.size(), 0);
    if (!sent) { WinHttpCloseHandle(hRequest); WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession); return false; }
    if (!WinHttpReceiveResponse(hRequest, NULL)) { WinHttpCloseHandle(hRequest); WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession); return false; }
    if (out_body) {
        DWORD dwSize = 0; out_body->clear();
        while (WinHttpQueryDataAvailable(hRequest, &dwSize) && dwSize > 0) {
            std::vector<char> buffer(dwSize);
            DWORD downloaded = 0;
            if (WinHttpReadData(hRequest, buffer.data(), dwSize, &downloaded)) out_body->append(buffer.data(), downloaded);
            else break;
        }
    }
    WinHttpCloseHandle(hRequest); WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession);
    return true;
}



std::string load_agent_conf() {
    AgentConf ac;
    std::ifstream cf("agent.conf");
    if (!cf) {
        // Create minimal agent.conf template for operator to fill
        std::ofstream of("agent.conf");
        of << "agent_id=agent-PLACEHOLDER\n";
        of << "agent_auth=\n";
        of << "server=http://127.0.0.1:5000\n";
        of << "server_auth=\n";
        of.close();
        return "agent-PLACEHOLDER";
    }
    std::string line, agentid;
    while (std::getline(cf, line)) {
        if (line.rfind("agent=", 0) == 0) agentid = trim(line.substr(6));
    }
    if (agentid.empty()) agentid = "agent-" + std::to_string((unsigned)time(nullptr));
    return agentid;
}


std::string sha256_hex(const std::string& data) {
    HCRYPTPROV hProv = 0;
    HCRYPTHASH hHash = 0;
    BYTE hash[32];
    DWORD hashLen = 0;
    std::string out;
    if (!CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) return "";
    if (!CryptCreateHash(hProv, CALG_SHA_256, 0, 0, &hHash)) { CryptReleaseContext(hProv, 0); return ""; }
    CryptHashData(hHash, (BYTE*)data.c_str(), (DWORD)data.size(), 0);
    hashLen = sizeof(hash);
    CryptGetHashParam(hHash, HP_HASHVAL, hash, &hashLen, 0);
    std::ostringstream oss;
    for (DWORD i = 0; i < hashLen; i++) oss << std::hex << std::setw(2) << std::setfill('0') << (int)hash[i];
    CryptDestroyHash(hHash); CryptReleaseContext(hProv, 0);
    return oss.str();
}

static std::string get_hostname() {
    char buf[256] = { 0 };
    DWORD size = sizeof(buf);
    if (GetComputerNameA(buf, &size)) {
        return std::string(buf, size);
    }
    return std::string("UNKNOWN");
}

double get_cpu_usage() {
    static FILETIME prevIdleTime = { 0,0 }, prevKernelTime = { 0,0 }, prevUserTime = { 0,0 };

    FILETIME idleTime, kernelTime, userTime;
    if (!GetSystemTimes(&idleTime, &kernelTime, &userTime)) return -1.0;

    ULONGLONG idle = (((ULONGLONG)idleTime.dwHighDateTime) << 32) | idleTime.dwLowDateTime;
    ULONGLONG kernel = (((ULONGLONG)kernelTime.dwHighDateTime) << 32) | kernelTime.dwLowDateTime;
    ULONGLONG user = (((ULONGLONG)userTime.dwHighDateTime) << 32) | userTime.dwLowDateTime;

    ULONGLONG prevIdle = (((ULONGLONG)prevIdleTime.dwHighDateTime) << 32) | prevIdleTime.dwLowDateTime;
    ULONGLONG prevKernel = (((ULONGLONG)prevKernelTime.dwHighDateTime) << 32) | prevKernelTime.dwLowDateTime;
    ULONGLONG prevUser = (((ULONGLONG)prevUserTime.dwHighDateTime) << 32) | prevUserTime.dwLowDateTime;

    ULONGLONG sys = (kernel - prevKernel) + (user - prevUser);
    ULONGLONG idleDiff = idle - prevIdle;

    prevIdleTime = idleTime;
    prevKernelTime = kernelTime;
    prevUserTime = userTime;

    if (sys == 0) return 0.0;
    return 100.0 * (sys - idleDiff) / sys;
}

struct MemInfo {
    uint64_t total;
    uint64_t free;
};

MemInfo get_memory_info() {
    MEMORYSTATUSEX mem;
    mem.dwLength = sizeof(mem);
    GlobalMemoryStatusEx(&mem);
    return { mem.ullTotalPhys, mem.ullAvailPhys };
}

static std::string get_os_version() {
    // Определяем функцию RtlGetVersion в ntdll.dll
    typedef LONG(WINAPI* RtlGetVersionPtr)(OSVERSIONINFOEXW*);
    HMODULE hNt = GetModuleHandleW(L"ntdll.dll");
    if (!hNt) return std::string("UNKNOWN");

    auto rtl = (RtlGetVersionPtr)GetProcAddress(hNt, "RtlGetVersion");
    if (!rtl) return std::string("UNKNOWN");

    OSVERSIONINFOEXW info;
    ZeroMemory(&info, sizeof(info));
    info.dwOSVersionInfoSize = sizeof(info);
    if (rtl(&info) == 0) {
        std::ostringstream oss;
        oss << "Windows " << info.dwMajorVersion << "." << info.dwMinorVersion << " (Build " << info.dwBuildNumber << ")";
        return oss.str();
    }
    return std::string("UNKNOWN");
}

static std::vector<std::string> list_processes() {
    std::vector<std::string> out;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return out;

    PROCESSENTRY32 pe;
    ZeroMemory(&pe, sizeof(pe));
    pe.dwSize = sizeof(pe);

    if (Process32First(snap, &pe)) {
#ifdef UNICODE
        // pe.szExeFile - wchar_t, конвертируем в UTF-8
        int needed = WideCharToMultiByte(CP_UTF8, 0, pe.szExeFile, -1, NULL, 0, NULL, NULL);
        if (needed > 0) {
            std::string s(needed, '\0');
            WideCharToMultiByte(CP_UTF8, 0, pe.szExeFile, -1, &s[0], needed, NULL, NULL);
            if (!s.empty() && s.back() == '\0') s.pop_back();
            out.push_back(s);
        }
#else
        out.emplace_back(pe.szExeFile);
#endif
        while (Process32Next(snap, &pe)) {
#ifdef UNICODE
            int needed = WideCharToMultiByte(CP_UTF8, 0, pe.szExeFile, -1, NULL, 0, NULL, NULL);
            if (needed > 0) {
                std::string s(needed, '\0');
                WideCharToMultiByte(CP_UTF8, 0, pe.szExeFile, -1, &s[0], needed, NULL, NULL);
                if (!s.empty() && s.back() == '\0') s.pop_back();
                out.push_back(s);
            }
#else
            out.emplace_back(pe.szExeFile);
#endif
        }
    }

    CloseHandle(snap);
    return out;
}


struct PerfSnapshot {
    double cpu_percent;
    SIZE_T mem_used_bytes;
    SIZE_T mem_total_bytes;
};

static PerfSnapshot sample_perf() {
    PerfSnapshot s = { 0.0, 0, 0 };

    // memory
    MEMORYSTATUSEX ms; ms.dwLength = sizeof(ms);
    if (GlobalMemoryStatusEx(&ms)) {
        s.mem_total_bytes = ms.ullTotalPhys;
        s.mem_used_bytes = ms.ullTotalPhys - ms.ullAvailPhys;
    }

    // cpu — вычисляем дельту через GetSystemTimes (работает на Win7+)
    static FILETIME prevIdle = { 0,0 }, prevKernel = { 0,0 }, prevUser = { 0,0 };
    FILETIME idleTime, kernelTime, userTime;
    if (GetSystemTimes(&idleTime, &kernelTime, &userTime)) {
        // текущие значения
        ULONGLONG idle = ((ULONGLONG)idleTime.dwHighDateTime << 32) | idleTime.dwLowDateTime;
        ULONGLONG kernel = ((ULONGLONG)kernelTime.dwHighDateTime << 32) | kernelTime.dwLowDateTime;
        ULONGLONG user = ((ULONGLONG)userTime.dwHighDateTime << 32) | userTime.dwLowDateTime;

        ULONGLONG prevIdleULL = ((ULONGLONG)prevIdle.dwHighDateTime << 32) | prevIdle.dwLowDateTime;
        ULONGLONG prevKernelULL = ((ULONGLONG)prevKernel.dwHighDateTime << 32) | prevKernel.dwLowDateTime;
        ULONGLONG prevUserULL = ((ULONGLONG)prevUser.dwHighDateTime << 32) | prevUser.dwLowDateTime;

        ULONGLONG sys = (kernel - prevKernelULL) + (user - prevUserULL);
        ULONGLONG idleDiff = idle - prevIdleULL;

        // сохраняем для следующего вызова
        prevIdle = idleTime; prevKernel = kernelTime; prevUser = userTime;

        if (sys > 0) {
            s.cpu_percent = 100.0 * (double)(sys - idleDiff) / (double)sys;
        }
        else {
            s.cpu_percent = 0.0;
        }
    }

    return s;
}

std::string get_unique_pc_id() {
    std::string hw_info = "";

    // Серийник материнки через реестр
    HKEY hKey;
    char buf[256]; DWORD bSize = sizeof(buf);
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "HARDWARE\\DESCRIPTION\\System\\BIOS", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        if (RegQueryValueExA(hKey, "BaseBoardSerialNumber", NULL, NULL, (BYTE*)buf, &bSize) == ERROR_SUCCESS)
            hw_info += std::string(buf, bSize);
        RegCloseKey(hKey);
    }

    // MAC адрес
    IP_ADAPTER_INFO info[16]; DWORD len = sizeof(info);
    if (GetAdaptersInfo(info, &len) == ERROR_SUCCESS) {
        for (int i = 0; i < 6; i++) {
            char m[3]; sprintf_s(m, "%02X", info[0].Address[i]);
            hw_info += m;
        }
    }

    // Имя ПК
    char compName[MAX_COMPUTERNAME_LENGTH + 1]; DWORD cSize = sizeof(compName);
    GetComputerNameA(compName, &cSize);
    hw_info += compName;

    return sha256_hex(hw_info);
}

std::string get_now_iso() {
    SYSTEMTIME st; GetSystemTime(&st);
    char buf[64];
    sprintf_s(buf, "%04d-%02d-%02dT%02d:%02d:%02dZ", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    return std::string(buf);
}


// heartbeat
void heartbeat(const std::string& server, const std::string& agent_id, const std::string& agent_auth) {
    std::ostringstream hb;
    hb << "{\"agent_id\":\"" << agent_id << "\"";
    if (!agent_auth.empty()) hb << ",\"agent_auth\":\"" << agent_auth << "\"";
    hb << "}";
    http_post_json(server, "/heartbeat", hb.str());
}

// register agent
void register_agent(const std::string& server, const std::string& agent_id, const std::string& agent_auth) {
    std::ostringstream js;
    js << "{\"agent_id\":\"" << agent_id << "\",\"name\":\"" << agent_id << "\"";
    if (!agent_auth.empty()) js << ",\"agent_auth\":\"" << agent_auth << "\"";
    js << "}";
    http_post_json(server, "/register_agent", js.str());
}

// poll task (placeholder, print)
void poll_task(const std::string& server, const std::string& agent_id, const std::string& agent_auth) {
    std::string path = "/get_task?agent=" + agent_id;
    if (!agent_auth.empty()) path += "&auth=" + agent_auth;
    std::string resp;
    if (http_get_string(server, path, resp) && !resp.empty()) {
        std::cout << "[TASK] got: " << resp << "\n";
        // парсинг и исполнение команд можно добавить здесь
    }
}

// ---- run command or script with timeout; supports .bat and powershell .ps1 callers ----
// Модифицированная функция выполнения скрипта с exit code
bool run_script_with_exitcode(const std::string& script_path, const std::string& shell_type,
    int timeout_sec, int& exit_code, bool& timed_out) {
    exit_code = -1;
    timed_out = false;

    std::wstring cmd_line;
    if (shell_type == "powershell") {
        // PowerShell с проверкой exit code
        std::wstring ps_path(script_path.begin(), script_path.end());
        cmd_line = L"powershell.exe -ExecutionPolicy Bypass -NoProfile -File \"" + ps_path + L"\"";
    }
    else {
        // CMD с проверкой exit code
        std::wstring bat_path(script_path.begin(), script_path.end());
        cmd_line = L"cmd.exe /c \"" + bat_path + L"\"";
    }

    STARTUPINFOW si = {};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;

    PROCESS_INFORMATION pi = {};

    if (!CreateProcessW(nullptr, &cmd_line[0], nullptr, nullptr, FALSE,
        CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi)) {
        return false;
    }

    // Ждём завершения с таймаутом
    DWORD wait_result = WaitForSingleObject(pi.hProcess, timeout_sec * 1000);

    if (wait_result == WAIT_TIMEOUT) {
        timed_out = true;
        TerminateProcess(pi.hProcess, 1);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        return false;
    }

    // Получаем exit code
    DWORD process_exit_code = 0;
    if (GetExitCodeProcess(pi.hProcess, &process_exit_code)) {
        exit_code = static_cast<int>(process_exit_code);
    }

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return true;
}

std::string load_agent_id() {
    std::ifstream f("agent.id");
    if (f) {
        std::string id; std::getline(f, id); return id;
    }
    GUID g;
    HRESULT hr = CoCreateGuid(&g);
    char buf[64];
    if (SUCCEEDED(hr)) {
        sprintf_s(buf, "agent-%08X", g.Data1);
    }
    else {
        // Если GUID не создаётся, используем fallback на ticks
        ULONGLONG ticks = GetTickCount64();
        sprintf_s(buf, "agent-%llX", (unsigned long long)ticks);
    }
    std::ofstream o("agent.id"); o << buf;
    return std::string(buf);
}

bool server_alive(const std::string& url) {
    std::string out;
    // Запрашиваем /server_info — это не требует agent/auth и подходит для "who is that server"
    if (!http_get_string(url, "/server_info", out)) return false;

    // Простейший разбор JSON: ищем поле server_auth
    std::string server_auth = extract_json_string(out, "server_auth");
    if (!server_auth.empty()) {
        // сервер отвечает так, как ожидается
        return true;
    }

    // если сервер_info вернул что-то, но без server_auth — всё равно считаем живым
    return !out.empty();
}

static std::string json_unescape(const std::string& s) {
    std::string out; out.reserve(s.size());
    for (size_t i = 0; i < s.size(); ++i) {
        char c = s[i];
        if (c == '\\' && i + 1 < s.size()) {
            char n = s[i + 1];
            if (n == 'n') { out.push_back('\n'); i++; }
            else if (n == 'r') { out.push_back('\r'); i++; }
            else if (n == 't') { out.push_back('\t'); i++; }
            else if (n == '\\') { out.push_back('\\'); i++; }
            else if (n == '"') { out.push_back('"'); i++; }
            else if (n == 'u' && i + 5 < s.size()) {
                unsigned int code = 0; bool ok = true;
                for (int k = 0; k < 4; ++k) {
                    char ch = s[i + 2 + k];
                    code <<= 4;
                    if (ch >= '0' && ch <= '9') code |= (ch - '0');
                    else if (ch >= 'a' && ch <= 'f') code |= (10 + ch - 'a');
                    else if (ch >= 'A' && ch <= 'F') code |= (10 + ch - 'A');
                    else { ok = false; break; }
                }
                if (ok && code < 0x80) { out.push_back((char)code); i += 5; }
                else { out.push_back('\\'); }
            }
            else { out.push_back(n); i++; }
        }
        else out.push_back(c);
    }
    return out;
}

// Вспомогательная функция для SHA256 байтов
std::vector<BYTE> sha256_bytes(const std::vector<BYTE>& data) {
    HCRYPTPROV hProv = 0;
    HCRYPTHASH hHash = 0;
    BYTE hash[32];
    DWORD hashLen = 32;

    if (!CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) {
        return {};
    }

    if (!CryptCreateHash(hProv, CALG_SHA_256, 0, 0, &hHash)) {
        CryptReleaseContext(hProv, 0);
        return {};
    }

    CryptHashData(hHash, data.data(), (DWORD)data.size(), 0);
    CryptGetHashParam(hHash, HP_HASHVAL, hash, &hashLen, 0);

    CryptDestroyHash(hHash);
    CryptReleaseContext(hProv, 0);

    return std::vector<BYTE>(hash, hash + hashLen);
}

std::string hmac_sha256_hex(const std::string& key_hex, const std::string& msg) {
    // Преобразуем hex ключ в байты
    std::vector<BYTE> keyBytes;
    for (size_t i = 0; i < key_hex.length(); i += 2) {
        std::string byteString = key_hex.substr(i, 2);
        BYTE byte = (BYTE)strtol(byteString.c_str(), NULL, 16);
        keyBytes.push_back(byte);
    }

    const int BLOCK_SIZE = 64;

    // Если ключ длиннее блока - хешируем его
    if (keyBytes.size() > BLOCK_SIZE) {
        keyBytes = sha256_bytes(keyBytes);
    }

    // Дополняем ключ нулями до размера блока
    keyBytes.resize(BLOCK_SIZE, 0);

    // Создаем ipad и opad
    std::vector<BYTE> ipad(BLOCK_SIZE, 0x36);
    std::vector<BYTE> opad(BLOCK_SIZE, 0x5C);
    std::vector<BYTE> innerKey(BLOCK_SIZE);
    std::vector<BYTE> outerKey(BLOCK_SIZE);

    for (int i = 0; i < BLOCK_SIZE; i++) {
        innerKey[i] = keyBytes[i] ^ ipad[i];
        outerKey[i] = keyBytes[i] ^ opad[i];
    }

    // Внутренний хеш
    std::vector<BYTE> innerMsg;
    innerMsg.insert(innerMsg.end(), innerKey.begin(), innerKey.end());
    innerMsg.insert(innerMsg.end(), msg.begin(), msg.end());
    std::vector<BYTE> innerHash = sha256_bytes(innerMsg);

    // Внешний хеш
    std::vector<BYTE> outerMsg;
    outerMsg.insert(outerMsg.end(), outerKey.begin(), outerKey.end());
    outerMsg.insert(outerMsg.end(), innerHash.begin(), innerHash.end());
    std::vector<BYTE> outerHash = sha256_bytes(outerMsg);

    // Конвертируем в hex
    std::ostringstream oss;
    for (BYTE b : outerHash) {
        oss << std::hex << std::setw(2) << std::setfill('0') << (int)b;
    }
    return oss.str();
}

// keepalive thread for a running task: sends update_status RUNNING every interval seconds
DWORD WINAPI keepalive_thread(LPVOID param) {
    // param is pointer to struct containing server, agent_id, agent_auth, task_id, interval
    struct KA { std::string server; std::string agent; std::string auth; std::string task; int interval; };
    KA* p = (KA*)param;
    std::ostringstream js;
    while (true) {
        Sleep(p->interval * 1000);
        std::ostringstream hb;
        hb << "{\"task_id\":\"" << p->task << "\",\"agent\":\"" << p->agent << "\",\"state\":\"RUNNING\",\"msg\":\"keepalive\",\"agent_auth\":\"" << p->auth << "\"}";
        std::string out;
        http_post_json(p->server, "/update_status", hb.str(), &out);
        // agent will stop keepalive when process sets flag to stop (we could add global flag but for simplicity the thread will be terminated by the process end)
    }
    return 0;
}

std::string discover_server_udp(int timeout_ms = 2000) {
    const char* msg = "DISCOVER";
    const int UDP_PORT = 37020;
    SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock == INVALID_SOCKET) return "";
    char broadcast = 1;
    setsockopt(sock, SOL_SOCKET, SO_BROADCAST, &broadcast, sizeof(broadcast));
    sockaddr_in addr; addr.sin_family = AF_INET; addr.sin_port = htons(UDP_PORT); addr.sin_addr.s_addr = INADDR_BROADCAST;
    int ret = sendto(sock, msg, (int)strlen(msg), 0, (sockaddr*)&addr, sizeof(addr));
    if (ret == SOCKET_ERROR) { closesocket(sock); return ""; }
    int ms = timeout_ms; setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&ms, sizeof(ms));
    char buf[512]; sockaddr_in from; int fromlen = sizeof(from);
    ret = recvfrom(sock, buf, sizeof(buf) - 1, 0, (sockaddr*)&from, &fromlen);
    if (ret == SOCKET_ERROR) { closesocket(sock); return ""; }
    buf[ret] = 0; std::string resp = buf; closesocket(sock); return resp;
}

void send_telemetry(const AgentConf& conf) {
    json j;
    j["agent_id"] = conf.agent_id;
    if (!conf.agent_auth.empty()) j["agent_auth"] = conf.agent_auth;
    j["hostname"] = get_hostname();

    // время в ISO (UTC)
    {
        auto now = std::chrono::system_clock::now();
        std::time_t t = std::chrono::system_clock::to_time_t(now);
        std::tm gm;
        gmtime_s(&gm, &t);
        char buf[64];
        std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &gm);
        j["time"] = buf;
    }

    // OS version (без GetVersionExA)
    j["os_version"] = get_os_version();

    // processes
    auto procs = list_processes();
    j["processes"] = procs;

    // perf snapshot
    PerfSnapshot p = sample_perf();
    j["perf"] = { {"cpu_percent", p.cpu_percent}, {"mem_used", (uint64_t)p.mem_used_bytes}, {"mem_total", (uint64_t)p.mem_total_bytes} };

    // sample system files (read-only listing of system dir names) - безопасно
    std::vector<std::string> sysfiles;
    WIN32_FIND_DATAA fd;
    HANDLE hFind = FindFirstFileA("C:\\Windows\\System32\\*", &fd);
    if (hFind != INVALID_HANDLE_VALUE) {
        do {
            if (strcmp(fd.cFileName, ".") != 0 && strcmp(fd.cFileName, "..") != 0) {
                sysfiles.emplace_back(fd.cFileName);
            }
        } while (FindNextFileA(hFind, &fd));
        FindClose(hFind);
    }
    j["sample_system_files"] = sysfiles;

    // Сериализуем и отправляем
    std::string payload = j.dump();
    std::string out;
    std::string path = "/telemetry";
    if (!http_post_json(conf.server, path, payload, &out)) {
        std::cerr << "[!] telemetry post failed\n";
    }
    else {
        std::cout << "[+] telemetry posted\n";
    }
}

std::string get_persistent_id() {
    std::string id_file = "agent.id";
    std::ifstream ifile(id_file);
    if (ifile) {
        std::string id;
        std::getline(ifile, id);
        return trim(id);
    }

    // Если файла нет — генерируем новый один раз на основе HWID
    std::string new_id = get_unique_pc_id().substr(0, 12); // Используем часть HWID
    std::ofstream ofile(id_file);
    ofile << new_id;
    return new_id;
}

std::string get_hardware_id() {
    std::string raw_data = "";

    // 1. Получаем серийный номер материнской платы из реестра
    HKEY hKey;
    char buf[256]; DWORD bSize = sizeof(buf);
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "HARDWARE\\DESCRIPTION\\System\\BIOS", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        if (RegQueryValueExA(hKey, "BaseBoardSerialNumber", NULL, NULL, (BYTE*)buf, &bSize) == ERROR_SUCCESS) {
            raw_data += std::string(buf, bSize);
        }
        RegCloseKey(hKey);
    }

    // 2. Получаем MachineGuid (уникален для каждой установки Windows)
    bSize = sizeof(buf);
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Cryptography", 0, KEY_READ | KEY_WOW64_64KEY, &hKey) == ERROR_SUCCESS) {
        if (RegQueryValueExA(hKey, "MachineGuid", NULL, NULL, (BYTE*)buf, &bSize) == ERROR_SUCCESS) {
            raw_data += std::string(buf, bSize);
        }
        RegCloseKey(hKey);
    }

    // 3. Если реестр не отдал данные (редкий случай), используем имя ПК как fallback
    if (raw_data.length() < 5) {
        char compName[MAX_COMPUTERNAME_LENGTH + 1]; DWORD cSize = sizeof(compName);
        GetComputerNameA(compName, &cSize);
        raw_data += compName;
    }

    // Хешируем полученную строку, чтобы получить красивый фиксированный ID
    return sha256_hex(raw_data).substr(0, 16); // Берем первые 16 символов хеша
}

json collect_processes() {
    json plist = json::array();
    HANDLE hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnap != INVALID_HANDLE_VALUE) {
        PROCESSENTRY32W pe; pe.dwSize = sizeof(pe);
        if (Process32FirstW(hSnap, &pe)) {
            do {
                std::wstring ws(pe.szExeFile);
                plist.push_back({
                    {"pid", pe.th32ProcessID},
                    {"name", std::string(ws.begin(), ws.end())},
                    {"threads", pe.cntThreads}
                    });
            } while (Process32NextW(hSnap, &pe));
        }
        CloseHandle(hSnap);
    }
    return plist;
}

// Проводник (листинг папки)
json collect_fs(std::string path) {
    if (path.empty()) path = "C:\\";
    json files = json::array();
    try {
        for (const auto& entry : std::filesystem::directory_iterator(path)) {
            files.push_back({
                {"name", entry.path().filename().string()},
                {"is_dir", entry.is_directory()},
                {"size", entry.is_regular_file() ? std::filesystem::file_size(entry) : 0}
                });
        }
    }
    catch (...) {}
    return { {"path", path}, {"items", files} };
}

// Детальный сбор процессов
json collect_processes_detailed() {
    json plist = json::array();
    HANDLE hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnap == INVALID_HANDLE_VALUE) return plist;

    PROCESSENTRY32W pe; pe.dwSize = sizeof(pe);
    if (Process32FirstW(hSnap, &pe)) {
        do {
            long long mem_usage = 0;
            HANDLE hProcess = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pe.th32ProcessID);
            if (hProcess) {
                PROCESS_MEMORY_COUNTERS pmc;
                if (GetProcessMemoryInfo(hProcess, &pmc, sizeof(pmc))) {
                    mem_usage = pmc.WorkingSetSize;
                }
                CloseHandle(hProcess);
            }
            std::wstring ws(pe.szExeFile);
            plist.push_back({
                {"pid", pe.th32ProcessID},
                {"name", std::string(ws.begin(), ws.end())},
                {"threads", pe.cntThreads},
                {"mem_mb", mem_usage / 1024 / 1024}
                });
        } while (Process32NextW(hSnap, &pe));
    }
    CloseHandle(hSnap);
    return plist;
}

// Детальный проводник
json collect_fs_detailed(std::string path) {
    json result;
    json items = json::array();
    if (path.empty() || path == "ROOT" || path == " Мой компьютер") {
        char drives[256];
        DWORD len = GetLogicalDriveStringsA(sizeof(drives), drives);
        if (len > 0) {
            for (char* d = drives; *d; d += strlen(d) + 1) {
                items.push_back({ {"name", std::string(d)}, {"is_dir", true}, {"size", 0} });
            }
        }
        result["path"] = "Мой компьютер";
    }
    else {
        try {
            std::filesystem::path p(path);
            if (std::filesystem::exists(p)) {
                for (const auto& entry : std::filesystem::directory_iterator(p, std::filesystem::directory_options::skip_permission_denied)) {
                    items.push_back({
                        {"name", entry.path().filename().string()},
                        {"is_dir", entry.is_directory()},
                        {"size", entry.is_regular_file() ? std::filesystem::file_size(entry) : 0}
                        });
                }
            }
            result["path"] = p.string();
        }
        catch (...) { result["error"] = "Access Denied"; }
    }
    result["items"] = items;
    return result;
}


std::string get_drive_type_universal() {
    HANDLE hDevice = CreateFileA("\\\\.\\PhysicalDrive0", 0, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (hDevice == INVALID_HANDLE_VALUE) return "Unknown";

    STORAGE_PROPERTY_QUERY query = { StorageDeviceSeekPenaltyProperty, PropertyStandardQuery };
    DEVICE_SEEK_PENALTY_DESCRIPTOR result = { 0 };
    DWORD bytes;
    bool is_ssd = false;
    // Работает на Win7 SP1, 8, 10, 11
    if (DeviceIoControl(hDevice, IOCTL_STORAGE_QUERY_PROPERTY, &query, sizeof(query), &result, sizeof(result), &bytes, NULL)) {
        if (!result.IncursSeekPenalty) is_ssd = true;
    }
    CloseHandle(hDevice);
    return is_ssd ? "SSD" : "HDD";
}

json get_all_disks_info() {
    json disks = json::array();
    char buffer[256];
    DWORD len = GetLogicalDriveStringsA(sizeof(buffer), buffer);

    if (len == 0 || len > sizeof(buffer)) return disks;

    char* drive = buffer;
    while (*drive) {
        // Проверяем только фиксированные диски (HDD/SSD), игнорируя флешки и CD-ROM
        if (GetDriveTypeA(drive) == DRIVE_FIXED) {
            ULARGE_INTEGER free, total;
            json disk_info;

            if (GetDiskFreeSpaceExA(drive, &free, &total, NULL)) {
                disk_info["drive"] = std::string(drive);
                disk_info["total_gb"] = total.QuadPart / 1024 / 1024 / 1024;
                disk_info["free_gb"] = free.QuadPart / 1024 / 1024 / 1024;

                // Для определения SSD/HDD используем ваш метод, 
                // но передаем правильный путь к физическому диску
                // (упрощенно оставим вызов вашей функции для первого диска или адаптируйте её)
                disk_info["type"] = get_drive_type_universal();

                disks.push_back(disk_info);
            }
        }
        drive += strlen(drive) + 1; // Переход к следующей строке в буфере
    }
    return disks;
}

// Сбор расширенных характеристик
json collect_specs_universal() {
    json info;

    // 1. ОС и Редакция через реестр (самый стабильный путь)
    char prodName[256] = { 0 }, displayVer[64] = { 0 };
    DWORD sz = 256; HKEY hKey;
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        RegQueryValueExA(hKey, "ProductName", NULL, NULL, (BYTE*)prodName, &sz);
        sz = 64;
        // Пробуем DisplayVersion (Win10/11), если нет - CSDVersion (Win7 SP)
        if (RegQueryValueExA(hKey, "DisplayVersion", NULL, NULL, (BYTE*)displayVer, &sz) != ERROR_SUCCESS) {
            RegQueryValueExA(hKey, "CSDVersion", NULL, NULL, (BYTE*)displayVer, &sz);
        }
        RegCloseKey(hKey);
    }

    // 2. Железо (WinAPI)
    SYSTEM_INFO si; GetNativeSystemInfo(&si);
    MEMORYSTATUSEX mem; mem.dwLength = sizeof(mem); GlobalMemoryStatusEx(&mem);
    ULARGE_INTEGER free, total; GetDiskFreeSpaceExA("C:\\", &free, &total, NULL);

    info["os_full"] = std::string(prodName) + " " + std::string(displayVer);
    info["arch"] = (si.wProcessorArchitecture == 9) ? "x64" : "x32";
    info["cores"] = si.dwNumberOfProcessors;
    info["ram_gb"] = mem.ullTotalPhys / 1024 / 1024 / 1024;
    info["disk_gb"] = total.QuadPart / 1024 / 1024 / 1024;
    info["disk_type"] = get_drive_type_universal();
    info["disks"] = get_all_disks_info();
    info["update_at"] = (long long)std::time(nullptr); // Время сбора в секундах

    return info;
}

// Логика "Один раз в сутки" в основном цикле
void check_and_send_specs(const AgentConf& conf) {
    static long long last_send_time = 0;
    long long now = (long long)std::time(nullptr);

    // 86400 секунд = 24 часа
    if (now - last_send_time > 3600) {
        json payload;
        payload["agent_id"] = conf.agent_id;
        payload["agent_auth"] = conf.agent_auth;
        payload["specs"] = collect_specs_universal();

        if (http_post_json(conf.server, "/telemetry", payload.dump())) {
            last_send_time = now;
            std::cout << "[+] Daily specs updated and sent." << std::endl;
        }
    }
}

// Эта функция заменяет старый основной цикл, но включает всю подготовительную логику
void agent_main_with_persistence()
{
    // ========== 1. ИНИЦИАЛИЗАЦИЯ (скопировано из старого agent_main) ==========
    g_stopEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr);
    DWORD dwProtocols = WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_2;
    WinHttpSetOption(NULL, WINHTTP_OPTION_SECURE_PROTOCOLS, &dwProtocols, sizeof(dwProtocols));
    bool logging_enabled = true;

    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return;

    std::ifstream cf("agent.conf");
    AgentConf conf;
    std::string agent_id = load_agent_conf();
    if (!cf) {
        std::cerr << "Please create agent.conf with lines: agent=..., server=..., agent_auth=..., server_auth=...\n";
        return;
    }

    int config_port = 0;
    agent_auth = load_secret(L"agent_auth", agent_auth_from_file);
    server_auth = load_secret(L"server_auth", server_auth_from_file);

    std::string line;
    while (std::getline(cf, line)) {
        if (line.find("agent_auth=") == 0) conf.agent_auth = trim(line.substr(11));
        if (line.find("server_auth=") == 0) conf.expected_server_auth = trim(line.substr(12));
        if (line.find("server=") == 0) {
            std::string srv = trim(line.substr(7));
            conf.server = srv;
            size_t colon = srv.find_last_of(':');
            if (colon != std::string::npos) config_port = std::stoi(srv.substr(colon + 1));
        }
    }
    conf.agent_id = get_hardware_id();
    std::cout << "[*] Hardware-bound ID: " << conf.agent_id << std::endl;

    // ========== 2. ПОИСК СЕРВЕРА (скопировано из старого agent_main) ==========
    while (true) {
        if (!conf.server.empty() && conf.server.find("127.0.0.1") == std::string::npos) {
            std::cout << "[?] Probing config server: " << conf.server << std::endl;
            if (server_alive(conf.server)) break;
        }

        std::cout << "[*] Scanning network (excluding VPN)..." << std::endl;
        std::string discovered = discover_server_smart(config_port, 3000);

        if (!discovered.empty()) {
            std::cout << "[+] DISCOVERED: " << discovered << std::endl;
            conf.server = discovered;
            if (server_alive(conf.server)) break;
        }

        std::cout << "[-] Server not found. Retrying in 10 Seconds..." << std::endl;
        Sleep(10000);
    }

    std::cout << "[!] Connected to " << conf.server << ". Starting main loop." << std::endl;

    // ========== 3. РЕГИСТРАЦИЯ (скопировано из старого agent_main) ==========
    json reg;
    reg["agent_id"] = conf.agent_id; reg["name"] = conf.agent_id;
    if (!conf.agent_auth.empty()) reg["agent_auth"] = conf.agent_auth;
    std::string regresp;
    http_post_json(conf.server, "/register_agent", reg.dump(), &regresp);

    // (В старом коде после регистрации шёл цикл while(true) — мы его заменяем на новый цикл)

    // ========== 4. НОВЫЙ ОСНОВНОЙ ЦИКЛ С ПЕРСИСТЕНТНОСТЬЮ ==========
    // Загружаем сохранённые задачи при старте
    std::vector<LocalTask> local_tasks = LoadLocalTasks();

    while (!g_stopRequested.load()) {
        try {
            // 1. ПРОВЕРЯЕМ ЛОКАЛЬНЫЕ ЗАДАЧИ
            auto now_str = get_now_iso();

            for (auto& local_task : local_tasks) {
                // Пропускаем задачи DONE
                if (local_task.status == "DONE") {
                    continue;
                }

                // Если задача RUNNING и время истекло - пробуем еще раз
                if (local_task.status == "RUNNING" && IsTaskExpired(local_task)) {
                    std::cout << "[!] Task " << local_task.task_id << " expired, retrying..." << std::endl;
                    local_task.status = "PENDING";
                    local_task.retry_count++;
                    local_task.deadline = CalculateDeadline(local_task.timeout_seconds);
                    SaveLocalTasks(local_tasks);
                }

                // Если задача PENDING - выполняем её
                if (local_task.status == "PENDING") {
                    std::cout << "[*] Executing local task: " << local_task.task_id << std::endl;

                    // Обновляем статус на RUNNING
                    local_task.status = "RUNNING";
                    local_task.deadline = CalculateDeadline(local_task.timeout_seconds);
                    SaveLocalTasks(local_tasks);

                    // Уведомляем сервер
                    std::ostringstream jsrun;
                    jsrun << "{\"task_id\":\"" << local_task.task_id
                        << "\",\"agent\":\"" << conf.agent_id
                        << "\",\"state\":\"RUNNING\",\"agent_time\":\"" << get_now_iso()
                        << "\",\"agent_auth\":\"" << conf.agent_auth << "\"}";
                    http_post_json(conf.server, "/update_status", jsrun.str());

                    // Выполняем задачу
                    if (local_task.task_type == "RUN_CMD") {
                        // Создаём временный файл
                        fs::path tmpdir = fs::temp_directory_path();
                        std::string ext = (local_task.shell == "powershell") ? ".ps1" : ".bat";
                        fs::path tmpfile = tmpdir / (local_task.task_id + ext);

                        {
                            std::ofstream of(tmpfile);
                            of << local_task.cmd;
                        }

                        int exit_code = -1;
                        bool timed_out = false;

                        // Выполняем с проверкой exit code
                        bool success = run_script_with_exitcode(
                            tmpfile.string(),
                            local_task.shell,
                            local_task.timeout_seconds,
                            exit_code,
                            timed_out
                        );

                        // Обрабатываем результат
                        std::string final_status;
                        if (timed_out) {
                            final_status = "TIMEOUT";
                            local_task.status = "PENDING";  // Будет повторена
                            local_task.retry_count++;
                        }
                        else if (exit_code != 0) {
                            final_status = "FAILED";
                            local_task.status = "FAILED";
                        }
                        else {
                            final_status = "DONE";
                            local_task.status = "DONE";
                        }

                        // Отправляем статус на сервер
                        std::ostringstream jsstatus;
                        jsstatus << "{\"task_id\":\"" << local_task.task_id
                            << "\",\"agent\":\"" << conf.agent_id
                            << "\",\"state\":\"" << final_status
                            << "\",\"msg\":\"exit_code=" << exit_code
                            << "\",\"agent_time\":\"" << get_now_iso()
                            << "\",\"agent_auth\":\"" << conf.agent_auth << "\"}";

                        std::string status_resp;
                        if (http_post_json(conf.server, "/update_status", jsstatus.str(), &status_resp)) {
                            // Проверяем подтверждение для DONE
                            if (final_status == "DONE") {
                                try {
                                    json j_resp = json::parse(status_resp);
                                    if (j_resp.value("confirmed", false)) {
                                        // Сервер подтвердил - удаляем из локального хранилища
                                        std::cout << "[+] Task " << local_task.task_id
                                            << " confirmed by server" << std::endl;
                                    }
                                    else {
                                        std::cout << "[!] Task " << local_task.task_id
                                            << " not confirmed, keeping DONE status" << std::endl;
                                    }
                                }
                                catch (...) {}
                            }
                        }

                        SaveLocalTasks(local_tasks);

                        // Удаляем временный файл
                        try { fs::remove(tmpfile); }
                        catch (...) {}
                    }
                }
            }

            // Очистка завершённых задач, подтверждённых сервером
            local_tasks.erase(
                std::remove_if(local_tasks.begin(), local_tasks.end(),
                    [](const LocalTask& t) {
                        return t.status == "DONE" && t.retry_count == 0;
                    }),
                local_tasks.end()
            );

            // 2. ПИНГ СЕРВЕРА
            std::ostringstream ping_json;
            ping_json << "{\"agent_id\":\"" << conf.agent_id
                << "\",\"agent_auth\":\"" << conf.agent_auth << "\"}";
            http_post_json(conf.server, "/ping", ping_json.str());

            // 3. ПОЛУЧЕНИЕ НОВЫХ ЗАДАЧ (только если нет активных)
            bool has_active_task = false;
            for (const auto& t : local_tasks) {
                if (t.status == "RUNNING" || t.status == "PENDING") {
                    has_active_task = true;
                    break;
                }
            }

            if (!has_active_task) {
                std::ostringstream req_json;
                req_json << "{\"agent_id\":\"" << conf.agent_id
                    << "\",\"agent_auth\":\"" << conf.agent_auth << "\"}";

                std::string resp;
                if (http_post_json(conf.server, "/get_task", req_json.str(), &resp) && !resp.empty()) {
                    try {
                        json j = json::parse(resp);

                        if (j.contains("task_id")) {
                            // Создаём новую локальную задачу
                            LocalTask new_task;
                            new_task.task_id = j.value("task_id", "");
                            new_task.cmd = j.value("cmd", "");
                            new_task.shell = j.value("shell", "cmd");
                            new_task.file_url = j.value("file_url", "");
                            new_task.save_path = j.value("save_path", "");
                            new_task.timeout_seconds = j.value("timeout_seconds", 300);
                            new_task.task_type = j.value("task_type", "RUN_CMD");
                            new_task.status = "PENDING";
                            new_task.received_at = get_now_iso();
                            new_task.deadline = CalculateDeadline(new_task.timeout_seconds);
                            new_task.retry_count = 0;

                            local_tasks.push_back(new_task);
                            SaveLocalTasks(local_tasks);

                            std::cout << "[+] New task received: " << new_task.task_id << std::endl;
                        }
                    }
                    catch (const std::exception& e) {
                        std::cerr << "[ERROR] Failed to parse task: " << e.what() << std::endl;
                    }
                }
            }

        }
        catch (const std::exception& e) {
            std::cerr << "[ERROR] Main loop exception: " << e.what() << std::endl;
        }

        // Ждём 60 секунд
        Sleep(60000);
    }

    // ========== 5. ЗАВЕРШЕНИЕ (WSACleanup и т.д. будут вызваны после выхода из цикла) ==========
    WSACleanup();
}

int agent_main() {
    g_stopEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr);
    DWORD dwProtocols = WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_2;
    WinHttpSetOption(NULL, WINHTTP_OPTION_SECURE_PROTOCOLS, &dwProtocols, sizeof(dwProtocols));
    bool logging_enabled = true; // Логирование

    WSADATA wsa; if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return 1;

    std::ifstream cf("agent.conf");
    AgentConf conf;
    std::string agent_id = load_agent_conf();
    if (!cf) {
        std::cerr << "Please create agent.conf with lines: agent=..., server=..., agent_auth=..., server_auth=...\n";
        return 1;
    }

    int config_port = 0;

    agent_auth = load_secret(L"agent_auth", agent_auth_from_file);
    server_auth = load_secret(L"server_auth", server_auth_from_file);

    std::string line;
    while (std::getline(cf, line)) {
        if (line.find("agent_auth=") == 0) conf.agent_auth = trim(line.substr(11));
        if (line.find("server_auth=") == 0) conf.expected_server_auth = trim(line.substr(12));
        if (line.find("server=") == 0) {
            std::string srv = trim(line.substr(7));
            conf.server = srv;
            // Выцепляем порт из конфига для фильтрации
            size_t colon = srv.find_last_of(':');
            if (colon != std::string::npos) config_port = std::stoi(srv.substr(colon + 1));
        }
    }
    conf.agent_id = get_hardware_id();
    std::cout << "[*] Hardware-bound ID: " << conf.agent_id << std::endl;

    // 2. ЦИКЛ ПОИСКА СЕРВЕРА
    while (true) {
        // Сначала проверяем сервер из конфига (если он не localhost)
        if (!conf.server.empty() && conf.server.find("127.0.0.1") == std::string::npos) {
            std::cout << "[?] Probing config server: " << conf.server << std::endl;
            if (server_alive(conf.server)) break;
        }

        // Если статика не ответила — ВКЛЮЧАЕМ СКАНЕР

        std::cout << "[*] Scanning network (excluding VPN)..." << std::endl;
        std::string discovered = discover_server_smart(config_port, 3000);

        if (!discovered.empty()) {
            std::cout << "[+] DISCOVERED: " << discovered << std::endl;
            conf.server = discovered;
            if (server_alive(conf.server)) break;
        }

        std::cout << "[-] Server not found. Retrying in 10 Seconds..." << std::endl;
        Sleep(10000);
    }

    // Далее идет регистрация и основной цикл...
    std::cout << "[!] Connected to " << conf.server << ". Starting main loop." << std::endl;

    json reg;
    reg["agent_id"] = conf.agent_id; reg["name"] = conf.agent_id;
    if (!conf.agent_auth.empty()) reg["agent_auth"] = conf.agent_auth;
    std::string regresp;
    http_post_json(conf.server, "/register_agent", reg.dump(), &regresp);

    std::string server = trim(conf.server);
    while (true) {
        if (conf.server.empty() || !server_alive(conf.server)) {
            std::cout << "[!] Server lost or not set. Searching..." << std::endl;
            conf.server = discover_server_smart(config_port); // config_port из парсера

            if (conf.server.empty()) {
                Sleep(5000);
                continue;
            }
        }



        // Попытка Heartbeat / Polling
        std::string resp;
        if (!http_get_string(conf.server, "/get_task?agent=" + conf.agent_id, resp)) {
            std::cout << "[!] Connection failed. Resetting server URL." << std::endl;
            conf.server = ""; // Сбрасываем URL, чтобы поиск начался заново
            Sleep(2000);
            continue;
        }
        if (server.empty()) {
            std::cout << "Searching for server in network (broadcast smart) ...\n";
            server = discover_server_smart(3000);
            if (server.empty()) {
                std::cout << "Smart discovery failed, trying UDP DISCOVER fallback ...\n";
                server = discover_server_udp(2000);
            }
        }
        if (!server.empty()) {
            std::cout << "Probing server: " << server << " ...\n";
            if (server_alive(server)) {
                std::cout << "Server found at: " << server << "\n";
                conf.server = server; // запомним найденный сервер
                break;
            }
            else {
                std::cout << "Probe failed for " << server << "\n";
                server.clear();
            }
        }

        std::cout << "Server not found. Retrying in 10s...\n";
        Sleep(10000);
    }

    // ---- регистрация (используем conf.server, которое либо из config, либо найденное)
    {
        std::ostringstream reg;
        reg << "{\"agent_id\":\"" << conf.agent_id << "\",\"name\":\"" << conf.agent_id << "\"";
        if (!conf.agent_auth.empty()) reg << ",\"agent_auth\":\"" << conf.agent_auth << "\"";
        reg << "}";
        std::string body;
        if (!http_post_json(conf.server, "/register_agent", reg.str(), &body)) {
            std::cerr << "Register failed (network) — will continue and retry in loop\n";
        }
        else {
            // server may reply with pending flag or ok
            // nothing else now
        }
    }


    // main loop
    agent_main_with_persistence();

    WSACleanup();
    return 0;
}

void agent_shutdown() {
    g_stopRequested.store(true);
    if (g_stopEvent)
        SetEvent(g_stopEvent);
}

SERVICE_STATUS_HANDLE g_serviceHandle;
SERVICE_STATUS g_serviceStatus;

void WINAPI ServiceCtrlHandler(DWORD ctrl) {
    if (ctrl == SERVICE_CONTROL_STOP) {
        g_serviceStatus.dwCurrentState = SERVICE_STOP_PENDING;
        SetServiceStatus(g_serviceHandle, &g_serviceStatus);

        agent_shutdown();

        g_serviceStatus.dwCurrentState = SERVICE_STOPPED;
        SetServiceStatus(g_serviceHandle, &g_serviceStatus);
    }
}

void WINAPI ServiceMain(DWORD argc, LPWSTR* argv) {
    g_serviceHandle = RegisterServiceCtrlHandlerW(L"RMMService", ServiceCtrlHandler);

    g_serviceStatus.dwServiceType = SERVICE_WIN32_OWN_PROCESS;
    g_serviceStatus.dwCurrentState = SERVICE_START_PENDING;
    SetServiceStatus(g_serviceHandle, &g_serviceStatus);

    // ЗАПУСКАЕМ ТЕ САМЫЕ СОТНИ СТРОК MAIN
    std::thread worker(agent_main);
    worker.detach();

    g_serviceStatus.dwCurrentState = SERVICE_RUNNING;
    SetServiceStatus(g_serviceHandle, &g_serviceStatus);

    // Держим ServiceMain живой, пока работает агент
    while (g_serviceStatus.dwCurrentState == SERVICE_RUNNING) {
        Sleep(1000);
    }
}


int install_service() {
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(nullptr, path, MAX_PATH);

    // Добавляем кавычки для защиты от пробелов в путях
    std::wstring binPath = L"\"";
    binPath += path;
    binPath += L"\"";

    SC_HANDLE scm = OpenSCManager(nullptr, nullptr, SC_MANAGER_CREATE_SERVICE);
    if (!scm) return 1;

    SC_HANDLE svc = CreateServiceW(
        scm, SERVICE_NAME, SERVICE_NAME, SERVICE_ALL_ACCESS,
        SERVICE_WIN32_OWN_PROCESS, SERVICE_AUTO_START, SERVICE_ERROR_NORMAL,
        binPath.c_str(), nullptr, nullptr, nullptr, L"NT AUTHORITY\\SYSTEM", nullptr
    );

    if (svc) {
        // Настройка авто-перезапуска при сбое
        SERVICE_FAILURE_ACTIONSW sfa{};
        SC_ACTION actions[1];
        actions[0].Type = SC_ACTION_RESTART;
        actions[0].Delay = 5000; // 5 сек
        sfa.cActions = 1;
        sfa.lpsaActions = actions;
        ChangeServiceConfig2W(svc, SERVICE_CONFIG_FAILURE_ACTIONS, &sfa);
        CloseServiceHandle(svc);
    }
    CloseServiceHandle(scm);
    return 0;
}

int wmain(int argc, wchar_t* argv[]) {
    g_baseDir = GetExecutableDir();
    WSADATA wsa; WSAStartup(MAKEWORD(2, 2), &wsa);

    // Если запущен под отладчиком Visual Studio или передан флаг
    if (IsDebuggerPresent() || (argc > 1 && wcscmp(argv[1], L"--console") == 0)) {
        return agent_main();
    }

    log_init(g_baseDir, true);

    // В остальных случаях — ведем себя как служба
    SERVICE_TABLE_ENTRYW table[] = {
        { (LPWSTR)L"RMMService", (LPSERVICE_MAIN_FUNCTIONW)ServiceMain },
        { nullptr, nullptr }
    };
    if (!StartServiceCtrlDispatcherW(table)) return GetLastError();
    return 0;
}
