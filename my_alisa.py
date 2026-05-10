def ask_alisa(command):
    command = command.lower().strip()

    if command == "hello":
        return "Привет, я Алиса."

    if command == "say hi":
        return "Hi!"

    if command == "open youtube":
        return "Команда получена: открыть YouTube."

    return "Алиса получила команду: " + command