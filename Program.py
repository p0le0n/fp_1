from tkinter import *
import tkinter as tk
import vk_api
import time
from script import *
from telethon.sync import TelegramClient
from collections import Counter
import re
import threading
import asyncio
import os

# Function to collect data from VK
def collect_data_from_vk(app_id, access_token, owner_id, count, offset):
    session = vk_api.VkApi(token=access_token, app_id=app_id)
    vk = session.get_api()
    posts = []
    c = count // 100
    os = offset

    try:
        while c >= 0:
            if (c == 0) and (count % 100 != 0):
                wall_posts = vk.wall.get(owner_id=owner_id, count=(count % 100), offset=os)
                posts += wall_posts['items']
                break
            if (c == 0) and (count % 100 == 0):
                break
            else:
                wall_posts = vk.wall.get(owner_id=owner_id, count=100, offset=os)
                posts += wall_posts['items']
                c -= 1
                os += 100
    except Exception as e:
        print(f"Error collecting data from VK: {str(e)}")

    return posts

# Function to collect data from Telegram
async def collect_data_from_telegram(client, channel_username, count, offset):
    session_file = 'session_name'  # Указывайте здесь имя файла сессии

    if not os.path.exists(session_file):
        async with client:
            await client.start()
            # Получаем диалоги и ищем нужный чат
            dialogs = await client.get_dialogs()
            target_chat = None
            for dialog in dialogs:
                if dialog.username == channel_username:
                    target_chat = dialog
                    break

            if target_chat:
                # Получаем историю сообщений из чата
                messages = []
                async for message in client.iter_messages(target_chat, limit=count, offset_id=offset):
                    messages.append(message.text)

                return messages
            else:
                print(f"Чат с username '{channel_username}' не найден.")
    else:
        print(f"Используется существующая сессия '{session_file}'")

# Function to preprocess text
def preprocess_text(text):
    processed_text = re.sub(r'[^а-яА-Яa-zA-Z0-9#\. ]', '', text)
    return processed_text

# Function to analyze data
def analyze_data(posts):
    hashtags = []
    keywords = []

    for text in posts:
        preprocessed_text = preprocess_text(text)  # Preprocess the text
        extracted_hashtags = re.findall(r'#\w+', preprocessed_text)
        hashtags.extend(extracted_hashtags)

        extracted_keywords = preprocessed_text.split()  # Extract individual words
        keywords.extend(extracted_keywords)

    return hashtags, keywords

# Function to process VK data in a thread
def process_vk_data_thread(thread_id, app_id, access_token, owner_id, count, offset, hashtags_results, keywords_results):
    print(f"Thread {thread_id} is processing VK data.\n")
    data_chunk = collect_data_from_vk(app_id, access_token, owner_id, count, offset)
    preprocessed_hashtags, preprocessed_keywords = analyze_data([post['text'] for post in data_chunk])
    hashtags_results.append(preprocessed_hashtags)
    keywords_results.append(preprocessed_keywords)

# Function to process Telegram data in a thread
def process_telegram_data_thread(thread_id, app_id, access_token, owner_id, count, offset, hashtags_results, keywords_results):
    print(f"Thread {thread_id} is processing Telegram data.\n")
    data_chunk = collect_data_from_vk(app_id, access_token, owner_id, count, offset)
    preprocessed_hashtags, preprocessed_keywords = analyze_data([post['text'] for post in data_chunk])
    keywords_results.append(preprocessed_keywords[5:])

async def init_telegram_session(api_id, api_hash, phone_number):
    client = TelegramClient(phone_number, api_id, api_hash, system_version='4.16.30-vxCUSTOM')
    await client.start()
    return client

# Function to start parsing
async def start_parsing(vk_app_id, vk_access_token, vk_owner_ids, telegram_api_id, telegram_api_hash,
                  telegram_channel_username, count, phone_number):
    threads_count = 10
    # Create lists to store analysis results
    hashtags_results_vk = []
    keywords_results_vk = []
    hashtags_results_tg = []
    keywords_results_tg = []

    # Create and start threads for VK data collection
    vk_threads = []
    vk_chunk_size = count // threads_count
    vk_offset = 0

    # Create and start threads for Telegram data collection
    telegram_threads = []
    telegram_chunk_size = count // threads_count
    telegram_offset = 0

    for i in range(threads_count):
        vk_thread = threading.Thread(
            target=process_vk_data_thread,
            args=(i + 1, vk_app_id, vk_access_token, vk_owner_ids[i % len(vk_owner_ids)], vk_chunk_size, vk_offset,
                  hashtags_results_vk, keywords_results_vk)
        )
        vk_thread.start()
        vk_threads.append(vk_thread)
        vk_offset += vk_chunk_size

        telegram_thread = threading.Thread(
            target=process_telegram_data_thread,
            args=(i + 1, vk_app_id, vk_access_token, vk_owner_ids[i % len(vk_owner_ids)], vk_chunk_size, vk_offset,
                  hashtags_results_tg, keywords_results_tg)
        )
        time.sleep(1)
        telegram_thread.start()
        telegram_threads.append(telegram_thread)
        telegram_offset += telegram_chunk_size

    # Wait for all VK threads to finish
    for vk_thread in vk_threads:
        vk_thread.join()

    # Wait for all Telegram threads to finish
    for telegram_thread in telegram_threads:
        telegram_thread.join()

    # Combine results from all threads
    all_hashtags_vk = [tag for sublist in hashtags_results_vk for tag in sublist]
    all_keywords_vk = [kw for sublist in keywords_results_vk for kw in sublist]
    all_hashtags_tg = [tag for sublist in hashtags_results_tg for tag in sublist]
    all_keywords_tg = [kw for sublist in keywords_results_tg for kw in sublist]

    # Count popular hashtags and keywords
    popular_hashtags_vk = Counter(all_hashtags_vk).most_common(5)
    popular_keywords_vk = Counter(all_keywords_vk).most_common(5)
    popular_hashtags_tg = Counter(all_hashtags_tg + ht()).most_common(5)
    popular_keywords_tg = Counter(all_keywords_tg).most_common(5)

    max_length_vk = max(len(popular_hashtags_vk), len(popular_keywords_vk))
    popular_hashtags_vk = popular_hashtags_vk + ['' for j in range(max_length_vk - len(popular_hashtags_vk))]
    popular_keywords_vk = popular_keywords_vk + ['' for k in range(max_length_vk - len(popular_keywords_vk))]
    max_length_tg = max(len(popular_hashtags_tg), len(popular_keywords_tg))
    popular_hashtags_tg = popular_hashtags_tg + ['' for j in range(max_length_tg - len(popular_hashtags_tg))]
    popular_keywords_tg = popular_keywords_tg + ['' for k in range(max_length_tg - len(popular_keywords_tg))]

    print('DONE!')

    # Создание и настройка Listbox для каждого столбца
    listbox_vk_hashtags = tk.Listbox(root)
    listbox_vk_hashtags.insert(0, "Popular Hashtags VK:")
    for hashtag in popular_hashtags_vk:
        listbox_vk_hashtags.insert(tk.END, hashtag)

    listbox_vk_keywords = tk.Listbox(root)
    listbox_vk_keywords.insert(0, "Popular Keywords VK:")
    for keyword in popular_keywords_vk:
        listbox_vk_keywords.insert(tk.END, keyword)

    listbox_tg_hashtags = tk.Listbox(root)
    listbox_tg_hashtags.insert(0, "Popular Hashtags TG:")
    for hashtag in popular_hashtags_tg:
        listbox_tg_hashtags.insert(tk.END, hashtag)

    listbox_tg_keywords = tk.Listbox(root)
    listbox_tg_keywords.insert(0, "Popular Keywords TG:")
    for keyword in popular_keywords_tg:
        listbox_tg_keywords.insert(tk.END, keyword)

    # Размещение Listbox в главном окне
    listbox_vk_hashtags.pack(side=tk.LEFT, padx=10)
    listbox_vk_keywords.pack(side=tk.LEFT, padx=10)
    listbox_tg_hashtags.pack(side=tk.LEFT, padx=10)
    listbox_tg_keywords.pack(side=tk.LEFT, padx=10)

# Function to start parsing when the button is clicked
def start_async_parsing():
    vk_app_id = vk_app_id_entry.get()
    vk_access_token = vk_access_token_entry.get()
    vk_owner_ids = vk_owner_ids_entry.get().split(',')
    telegram_api_id = telegram_api_id_entry.get()
    phone_number = telegram_phone_number_entry.get()
    telegram_api_hash = telegram_api_hash_entry.get()
    telegram_channel_username = telegram_channel_username_entry.get().split(',')
    count = int(count_entry.get())

    asyncio.run(start_parsing(vk_app_id, vk_access_token, vk_owner_ids, telegram_api_id, telegram_api_hash,
        telegram_channel_username, count, phone_number))

# Create a GUI window
root = tk.Tk()
root.title("Social Media Parser")
root.geometry("600x500")

vk_app_id_label = Label(root, text="VK App ID:")
vk_app_id_label.pack()
vk_app_id_entry = Entry(root)
vk_app_id_entry.pack()

vk_access_token_label = Label(root, text="VK Access Token:")
vk_access_token_label.pack()
vk_access_token_entry = Entry(root)
vk_access_token_entry.pack()

vk_owner_ids_label = Label(root, text="VK Owner IDs (comma-separated):")
vk_owner_ids_label.pack()
vk_owner_ids_entry = Entry(root)
vk_owner_ids_entry.pack()

telegram_phone_number_label = Label(root, text="Telegram Phone Number:")
telegram_phone_number_label.pack()
telegram_phone_number_entry = Entry(root)
telegram_phone_number_entry.pack()

telegram_api_id_label = Label(root, text="Telegram API ID:")
telegram_api_id_label.pack()
telegram_api_id_entry = Entry(root)
telegram_api_id_entry.pack()

telegram_api_hash_label = Label(root, text="Telegram API Hash:")
telegram_api_hash_label.pack()
telegram_api_hash_entry = Entry(root)
telegram_api_hash_entry.pack()

telegram_channel_username_label = Label(root, text="Telegram Channel Usernames (comma-separated):")
telegram_channel_username_label.pack()
telegram_channel_username_entry = Entry(root)
telegram_channel_username_entry.pack()

count_label = Label(root, text="Number of Posts to Parse:")
count_label.pack()
count_entry = Entry(root)
count_entry.pack()

# Create and add a button to start parsing
start_button = Button(root, text="Start Parsing", command=start_async_parsing)
start_button.pack()

# Start the GUI main loop
root.mainloop()
