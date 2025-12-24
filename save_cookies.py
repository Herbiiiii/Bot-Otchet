#!/usr/bin/env python3
"""
Скрипт для разового сохранения cookies Google после успешного входа в Мозаику.
Запустите этот скрипт локально, войдите в Мозаику, и cookies будут сохранены.
"""
import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from services.selenium_collector import SeleniumCollector
from config.settings import ADMIN_EMAIL, ADMIN_PASSWORD

def main():
    """Сохраняет cookies после успешного входа"""
    print("=" * 60)
    print("Скрипт сохранения cookies для Мозаики")
    print("=" * 60)
    print()
    
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("❌ Ошибка: ADMIN_EMAIL и ADMIN_PASSWORD должны быть установлены в .env")
        return
    
    print(f"📧 Email: {ADMIN_EMAIL}")
    print("🔐 Пароль: ***")
    print()
    print("Инициализация Selenium...")
    
    collector = SeleniumCollector(ADMIN_EMAIL, ADMIN_PASSWORD)
    
    try:
        print("\n🔑 Вход в Мозаику...")
        print("   (Если Google потребует 2FA или challenge, выполните проверку вручную)")
        
        if collector.login():
            print("\n✅ Вход успешен!")
            print("💾 Сохранение cookies...")
            
            # Сохраняем cookies
            collector._save_cookies()
            
            cookies_file = collector.cookies_file
            if cookies_file.exists():
                with open(cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                
                print(f"\n✅ Cookies успешно сохранены!")
                print(f"📁 Файл: {cookies_file}")
                print(f"🍪 Количество cookies: {len(cookies)}")
                print()
                print("=" * 60)
                print("Следующие шаги:")
                print("=" * 60)
                print(f"1. Скопируйте файл cookies в Docker:")
                print(f"   docker cp {cookies_file} bot-otchet:/app/data/google_cookies.json")
                print()
                print("2. Или убедитесь, что файл находится в:")
                print(f"   {cookies_file}")
                print("   (он будет автоматически монтироваться через volume)")
                print()
                print("3. Перезапустите Docker контейнер:")
                print("   docker-compose restart")
                print("=" * 60)
            else:
                print("❌ Ошибка: Файл cookies не был создан")
        else:
            print("\n❌ Не удалось войти в Мозаику")
            print("   Проверьте учетные данные и попробуйте снова")
            print("   Если Google требует 2FA, выполните проверку вручную в браузере")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔒 Закрытие браузера...")
        collector.close()
        print("✅ Готово!")

if __name__ == '__main__':
    main()

