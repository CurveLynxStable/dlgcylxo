#!/bin/bash

# Циклически спрашиваем подтверждение генерации CA-сертификата и ключа
while true; do
    read -p "Do you want to generate ca cert and key? [yes/no] " yn
    case $yn in
        [Yy]* ) break;; # Если пользователь ввёл Y или y — выходим из цикла и продолжаем
        [Nn]* ) exit 1;; # Если пользователь ввёл N или n — выходим из скрипта
        * ) echo "Please answer yes or no.";; # Иначе просим ввести ещё раз
    esac
done

# Имя временного конфигурационного файла
TEMP_CONF_FILE="_genca_temp_config.cnf"
# trap гарантирует удаление временного файла при любом выходе из скрипта
trap 'rm -f "$TEMP_CONF_FILE"' EXIT

echo "Combining openssl.cnf and v3_ca.cnf into $TEMP_CONF_FILE..."
# Объединяем содержимое openssl.cnf и v3_ca.cnf во временный конфиг
cat openssl.cnf v3_ca.cnf > "$TEMP_CONF_FILE"
# Проверяем успешность предыдущей команды
if [ $? -ne 0 ]; then
    echo "Error: Failed to create temporary config file '$TEMP_CONF_FILE'."
    exit 1 # При неудаче выводим ошибку и выходим
fi
echo "Temporary config file created successfully."

echo "Generating CA private key (ca.key)..."
# Генерируем 2048-битный приватный ключ RSA для CA
openssl genrsa -out ca.key 2048
if [ $? -ne 0 ]; then
    echo "Error: Failed to generate CA key."
    exit 1
fi
echo "CA key generated."

echo "Generating CA certificate (ca.crt) using $TEMP_CONF_FILE..."
# Создаём самоподписанный CA-сертификат из ключа и временного конфига
# -new: новый запрос сертификата (здесь сразу генерируется сертификат)
# -x509: вывести самоподписанный сертификат вместо запроса
# -extensions v3_ca: использовать расширения из секции v3_ca
# -days 36500: срок действия сертификата (~100 лет)
# -key ca.key: файл приватного ключа
# -out ca.crt: выходной файл сертификата
# -config "$TEMP_CONF_FILE": конфигурационный файл OpenSSL
openssl req -new -x509 -extensions v3_ca -days 36500 -key ca.key -out ca.crt -config "$TEMP_CONF_FILE"
if [ $? -ne 0 ]; then
    echo "Error: Failed to generate CA certificate."
    exit 1
fi
echo "CA certificate generated successfully: ca.crt"
echo "Script finished."
# trap автоматически удалит $TEMP_CONF_FILE при завершении скрипта
