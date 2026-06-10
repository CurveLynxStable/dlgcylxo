#!/bin/bash

# Функция: вывести ошибку и выйти из скрипта
# Аргумент $1: строка с текстом ошибки
error_exit() {
    echo "Ошибка: $1" >&2 # Выводим ошибку в stderr
    # Если временный конфиг задан и существует — удаляем
    if [ ! -z "$TEMP_CONF_FILE" ] && [ -f "$TEMP_CONF_FILE" ]; then
        rm -f "$TEMP_CONF_FILE"
    fi
    exit 1 # Код выхода 1 — ошибка
}

# --- Начало основной логики скрипта ---

# Первый аргумент командной строки — префикс имени сертификата (например, api.openai.com)
NAME="$1"
TEMP_CONF_FILE="" # Инициализируем переменную, чтобы trap не падал при отсутствии значения

# Проверяем, что параметр NAME задан
if [ -z "$NAME" ]; then
    error_exit "Необходимо указать параметр NAME (например, api.openai.com). Использование: $0 <domain_name_prefix>"
fi

# Имена требуемых конфигурационных файлов
OPENSSL_CNF="openssl.cnf"
V3_REQ_CNF="v3_req.cnf"
NAME_CNF="$NAME.cnf"
NAME_SUBJ="$NAME.subj"
CA_CERT="ca.crt"
CA_KEY="ca.key"

# Проверяем наличие всех требуемых входных файлов в текущем каталоге
echo "INFO: Проверяем требуемые файлы..."
for f in "$OPENSSL_CNF" "$V3_REQ_CNF" "$NAME_CNF" "$NAME_SUBJ" "$CA_CERT" "$CA_KEY"; do
    if [ ! -f "$f" ]; then
        error_exit "Требуемый файл '$f' не найден в текущем каталоге ($(pwd))."
    fi
done
echo "INFO: Все требуемые файлы на месте."

# Уникальное имя временного конфига (PID $$ обеспечивает уникальность)
TEMP_CONF_FILE="_temp_openssl_config_$$.cnf"
# trap: удаляем временный файл при любом выходе (успех, ошибка, прерывание)
trap 'echo "INFO: Удаляем временный файл $TEMP_CONF_FILE..."; rm -f "$TEMP_CONF_FILE"' EXIT

echo "INFO: Объединяем '$OPENSSL_CNF', '$V3_REQ_CNF' и '$NAME_CNF' во временный файл '$TEMP_CONF_FILE'..."
# Объединяем несколько конфигов OpenSSL в один временный файл
cat "$OPENSSL_CNF" "$V3_REQ_CNF" "$NAME_CNF" > "$TEMP_CONF_FILE"
if [ $? -ne 0 ]; then # Проверяем успешность предыдущей команды (cat)
    error_exit "Не удалось создать временный конфигурационный файл '$TEMP_CONF_FILE'."
fi
echo "INFO: Временный конфигурационный файл создан."

# Читаем subject сертификата из файла $NAME.subj
SUBJECT_INFO=$(cat "$NAME.subj")
if [ -z "$SUBJECT_INFO" ]; then # Проверяем, что содержимое прочитано
    error_exit "Файл subject '$NAME.subj' пуст или не читается."
fi
echo "INFO: Subject из '$NAME.subj': $SUBJECT_INFO"

echo "INFO: Генерируем приватный ключ '$NAME.key' (RSA 2048 бит)..."
# Генерируем приватный ключ сервера
openssl genrsa -out "$NAME.key" 2048
if [ $? -ne 0 ]; then error_exit "Не удалось сгенерировать приватный ключ '$NAME.key'."; fi

echo "INFO: Преобразуем приватный ключ '$NAME.key' в формат PKCS#8..."
# Преобразуем ключ в PKCS#8 (обычно для лучшей совместимости)
openssl pkcs8 -topk8 -nocrypt -in "$NAME.key" -out "$NAME.key.pk8"
if [ $? -ne 0 ]; then error_exit "Не удалось преобразовать приватный ключ '$NAME.key' в формат PKCS#8."; fi
rm "$NAME.key" # Удаляем ключ в исходном формате
mv "$NAME.key.pk8" "$NAME.key" # Переименовываем PKCS#8-ключ обратно
echo "INFO: Приватный ключ '$NAME.key' готов."

echo "INFO: Генерируем запрос на подпись сертификата (CSR) '$NAME.csr'..."
# Генерируем CSR из временного конфига и прочитанного subject
# MSYS_NO_PATHCONV=1 отключает нежелательное преобразование путей MinGW/MSYS для -subj
MSYS_NO_PATHCONV=1 openssl req -reqexts v3_req -sha256 -new -key "$NAME.key" -out "$NAME.csr" \
    -config "$TEMP_CONF_FILE" \
    -subj "$SUBJECT_INFO"
if [ $? -ne 0 ]; then error_exit "Не удалось сгенерировать CSR '$NAME.csr'."; fi
echo "INFO: CSR '$NAME.csr' успешно создан."

echo "INFO: Подписываем сертификат '$NAME.crt' с помощью CA..."
# Подписываем CSR сертификатом и ключом CA, получая итоговый сертификат сервера
# Для -extfile также используется объединённый временный конфиг
openssl x509 -req -extensions v3_req -days 365 -sha256 \
    -in "$NAME.csr" \
    -CA "$CA_CERT" \
    -CAkey "$CA_KEY" \
    -CAcreateserial \
    -out "$NAME.crt" \
    -extfile "$TEMP_CONF_FILE"
if [ $? -ne 0 ]; then error_exit "Не удалось подписать сертификат '$NAME.crt'."; fi

echo "INFO: Сертификат '$NAME.crt' успешно создан."
# Файл CSR ($NAME.csr) по умолчанию сохраняется; раскомментируйте строку ниже для удаления
# echo "INFO: (опционально) удаляем '$NAME.csr'..."
# rm -f "$NAME.csr"

# Временный конфиг $TEMP_CONF_FILE будет удалён командой trap при выходе
echo "INFO: Скрипт для '$NAME' завершён."
exit 0 # Код выхода 0 — успех
