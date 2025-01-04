import os
from tkinter import Tk
from tkinter.filedialog import askdirectory

# Инициализация Tkinter
Tk().withdraw()  # Скрыть главное окно

# Запрос папки с изображениями
images_folder = askdirectory(title="Выберите папку с изображениями")
# Запрос папки с текстовыми файлами
labels_folder = askdirectory(title="Выберите папку с текстовыми файлами")

# Запрашиваем у пользователя новое имя для файлов
new_name = input("Введите новое имя для файлов: ")

# Получаем список файлов в папке images
image_files = {os.path.splitext(f)[0] for f in os.listdir(images_folder) if f.endswith(('.jpg', '.jpeg'))}

# Получаем список файлов в папке labels
label_files = {os.path.splitext(f)[0] for f in os.listdir(labels_folder) if f.endswith('.txt')}

# Находим совпадения
matching_files = image_files.intersection(label_files)

# Переименовываем совпадающие файлы
if matching_files:
    print("Найденные совпадения:")
    for index, file in enumerate(matching_files, start=1):
        # Переименование изображений
        old_image_path = os.path.join(images_folder, f"{file}.jpg")
        new_image_path = os.path.join(images_folder, f"{new_name}_{index}.jpg")
        
        old_label_path = os.path.join(labels_folder, f"{file}.txt")
        new_label_path = os.path.join(labels_folder, f"{new_name}_{index}.txt")
        
        # Переименование файлов
        os.rename(old_image_path, new_image_path)
        os.rename(old_label_path, new_label_path)
        
        print(f"Переименованы: {old_image_path} -> {new_image_path}")
        print(f"Переименованы: {old_label_path} -> {new_label_path}")
else:
    print("Совпадений не найдено.")
