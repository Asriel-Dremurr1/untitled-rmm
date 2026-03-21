#include <windows.h>
#include <iostream>
#include <string>
#include <filesystem>
#include <fstream>
#include <vector>
#include <sddl.h>
#include <aclapi.h>

namespace fs = std::filesystem;

// Константы путей
const std::wstring SERVICE_NAME = L"RMMService";
const std::wstring INSTALL_PATH = L"C:\\Program Files\\RMMAgent";
const std::wstring REG_PATH = L"SOFTWARE\\MYRMM\\Secrets";
const std::wstring AGENT_EXE = L"HomeDomainClient.exe";
const std::wstring AGENT_CONF = L"agent.conf";

// Функция для установки прав доступа на раздел реестра.



// !!!!НЕ РАБОТАЕТ НЕ УЧИТЫВАТЬ!!!!
void SetRegistryACL(const std::wstring& subKey) {
    PSECURITY_DESCRIPTOR psd = NULL;
    // SYSTEM: Full, Admins: Read/Delete, Everyone: Deny
    if (ConvertStringSecurityDescriptorToSecurityDescriptorW(
        L"D:P(D;;GA;;;WD)(A;;GA;;;SY)(A;;SDGR;;;BA)",
        SDDL_REVISION_1, &psd, NULL))
    {
        HKEY hKey;
        // Открываем с флагом доступа к x64 ветке (для надежности)
        if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, subKey.c_str(), 0, WRITE_DAC | KEY_WOW64_64KEY, &hKey) == ERROR_SUCCESS) {
            RegSetKeySecurity(hKey, DACL_SECURITY_INFORMATION, psd);
            RegCloseKey(hKey);
        }
        // Также для x86 ветки (SysWOW64)
        if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, subKey.c_str(), 0, WRITE_DAC | KEY_WOW64_32KEY, &hKey) == ERROR_SUCCESS) {
            RegSetKeySecurity(hKey, DACL_SECURITY_INFORMATION, psd);
            RegCloseKey(hKey);
        }
        LocalFree(psd);
    }
}

// Парсинг agent.conf и запись секретов в реестр
void MigrateConfToRegistry(const fs::path& confPath) {
    std::ifstream file(confPath);
    if (!file.is_open()) return;

    std::string line;
    HKEY hKey64, hKey32;

    // Создаем ключи в обеих ветках реестра (для x64 и x86 приложений)
    RegCreateKeyExW(HKEY_LOCAL_MACHINE, REG_PATH.c_str(), 0, NULL, 0, KEY_WRITE | KEY_WOW64_64KEY, NULL, &hKey64, NULL);
    RegCreateKeyExW(HKEY_LOCAL_MACHINE, REG_PATH.c_str(), 0, NULL, 0, KEY_WRITE | KEY_WOW64_32KEY, NULL, &hKey32, NULL);

    while (std::getline(file, line)) {
        size_t sep = line.find('=');
        if (sep != std::string::npos) {
            std::string key = line.substr(0, sep);
            std::string val = line.substr(sep + 1);

            // Записываем только важные секреты
            if (key == "agent_auth" || key == "server_auth") {
                RegSetValueExA(hKey64, key.c_str(), 0, REG_SZ, (BYTE*)val.c_str(), (DWORD)val.size() + 1);
                RegSetValueExA(hKey32, key.c_str(), 0, REG_SZ, (BYTE*)val.c_str(), (DWORD)val.size() + 1);
            }
        }
    }
    if (hKey64) RegCloseKey(hKey64);
    if (hKey32) RegCloseKey(hKey32);

    SetRegistryACL(REG_PATH);
}

void Install() {
    std::wcout << L"[*] Начало установки..." << std::endl;

    // Пути к системным папкам
    wchar_t sys32[MAX_PATH], sysWow64[MAX_PATH];
    GetSystemDirectoryW(sys32, MAX_PATH); // C:\Windows\System32
    GetSystemWow64DirectoryW(sysWow64, MAX_PATH); // C:\Windows\SysWOW64

    try {
        // 0. Создание основной папки и копирование
        if (!fs::exists(INSTALL_PATH)) fs::create_directories(INSTALL_PATH);

        fs::path srcExe = fs::current_path() / L"agent" / AGENT_EXE;
        fs::path srcConf = fs::current_path() / L"agent" / AGENT_CONF;

        fs::copy_file(srcExe, INSTALL_PATH + L"\\" + AGENT_EXE, fs::copy_options::overwrite_existing);
        fs::copy_file(srcConf, INSTALL_PATH + L"\\" + AGENT_CONF, fs::copy_options::overwrite_existing);

        // 1. КОПИРОВАНИЕ В СИСТЕМНЫЕ ПАПКИ (Костыль для путей службы)
        std::wcout << L"[*] Копирование конфига в системные папки..." << std::endl;
        fs::copy_file(srcConf, std::wstring(sys32) + L"\\" + AGENT_CONF, fs::copy_options::overwrite_existing);
        if (wcslen(sysWow64) > 0) {
            fs::copy_file(srcConf, std::wstring(sysWow64) + L"\\" + AGENT_CONF, fs::copy_options::overwrite_existing);
        }

        // 2. Миграция данных в реестр
        MigrateConfToRegistry(srcConf);

    }
    catch (const std::exception& e) {
        std::cerr << "Ошибка при работе с файлами: " << e.what() << std::endl;
        return;
    }

    // 3. Установка службы
    SC_HANDLE scm = OpenSCManager(NULL, NULL, SC_MANAGER_CREATE_SERVICE);
    if (!scm) return;

    // Путь к EXE обязательно в кавычках (фикс ошибки 193)
    std::wstring binPath = L"\"" + INSTALL_PATH + L"\\" + AGENT_EXE + L"\"";

    SC_HANDLE svc = CreateServiceW(
        scm, SERVICE_NAME.c_str(), SERVICE_NAME.c_str(),
        SERVICE_ALL_ACCESS, SERVICE_WIN32_OWN_PROCESS,
        SERVICE_AUTO_START, SERVICE_ERROR_NORMAL,
        binPath.c_str(), NULL, NULL, NULL, L"NT AUTHORITY\\SYSTEM", NULL
    );

    if (svc) {
        // Настройка авто-перезапуска при падении
        SERVICE_FAILURE_ACTIONS sfa;
        SC_ACTION actions[1];
        actions[0].Type = SC_ACTION_RESTART;
        actions[0].Delay = 5000;
        sfa.dwResetPeriod = 86400;
        sfa.lpRebootMsg = NULL;
        sfa.lpCommand = NULL;
        sfa.cActions = 1;
        sfa.lpsaActions = actions;
        ChangeServiceConfig2(svc, SERVICE_CONFIG_FAILURE_ACTIONS, &sfa);

        // 4. Запуск
        StartService(svc, 0, NULL);
        std::wcout << L"[+] Служба успешно установлена и запущена!" << std::endl;
        CloseServiceHandle(svc);
    }
    else {
        std::cerr << "Не удалось создать службу. Код: " << GetLastError() << std::endl;
    }
    CloseServiceHandle(scm);
}

int main(int argc, char* argv[]) {
    setlocale(LC_ALL, "Russian");
    Install();
    std::cout << "Нажмите Enter для выхода...";
    std::cin.get();
    return 0;
}
