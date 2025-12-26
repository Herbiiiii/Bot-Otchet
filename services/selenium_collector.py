import time
import logging
import json
import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from typing import Optional, Dict
import sys
import io

logger = logging.getLogger(__name__)

class SeleniumCollector:
    """Класс для сбора отчетов через Selenium"""
    
    def __init__(self, email: str, password: str):
        """
        Инициализация Selenium драйвера для работы с Мозаикой
        
        Args:
            email: Email для входа в Мозаику
            password: Пароль для входа в Мозаику
        """
        if not email:
            raise ValueError("Email is required for SeleniumCollector")
        if not password:
            raise ValueError("Password is required for SeleniumCollector")
        
        self.email = email
        self.password = password
        self.driver = None
        self.wait = None
        # Путь к файлу cookies (в Docker - /app/data, локально - ./data)
        if sys.platform == 'win32' or not Path("/app").exists():
            self.cookies_file = Path("data/google_cookies.json")
        else:
            self.cookies_file = Path("/app/data/google_cookies.json")
        
        # Очищаем зависшие процессы Chrome перед инициализацией (только в Linux)
        if sys.platform != 'win32':
            self._cleanup_stale_chrome_processes()
        
        self._init_driver()
    
    def _cleanup_stale_chrome_processes(self):
        """Очищает зависшие процессы Chrome перед инициализацией нового браузера"""
        try:
            import subprocess
            import time
            # Проверяем, есть ли процессы Chrome
            result = subprocess.run(['ps', 'aux'], 
                                  capture_output=True, 
                                  text=True,
                                  timeout=2)
            if result.returncode == 0:
                chrome_processes = [line for line in result.stdout.split('\n') 
                                  if 'chrome' in line.lower() and 'grep' not in line.lower()]
                # Очищаем только если процессов много (более 5) - это явно зависшие
                # Если процессов мало, возможно они еще закрываются
                if len(chrome_processes) > 5:
                    logger.info(f"Found {len(chrome_processes)} stale Chrome processes (>{5}), cleaning up...")
                    # Более мягкое закрытие сначала
                    subprocess.run(['pkill', '-TERM', '-f', 'chrome'], 
                                 capture_output=True, 
                                 timeout=2,
                                 check=False)
                    time.sleep(1)  # Даем время на корректное закрытие
                    # Только если процессы остались - убиваем принудительно
                    result2 = subprocess.run(['ps', 'aux'], 
                                            capture_output=True, 
                                            text=True,
                                            timeout=2)
                    if result2.returncode == 0:
                        remaining = [line for line in result2.stdout.split('\n') 
                                    if 'chrome' in line.lower() and 'grep' not in line.lower()]
                        if len(remaining) > 5:
                            logger.warning(f"Still {len(remaining)} Chrome processes, forcing kill...")
                            subprocess.run(['pkill', '-9', '-f', 'chrome'], 
                                         capture_output=True, 
                                         timeout=2,
                                         check=False)
                            time.sleep(0.5)
        except Exception as e:
            logger.debug(f"Could not cleanup stale Chrome processes: {e}")
    
    def _init_driver(self):
        """Инициализация Chrome драйвера"""
        try:
            chrome_options = Options()
            
            # Настройки для Windows
            if sys.platform == 'win32':
                chrome_options.add_argument('--start-maximized')
            else:
                # Для Linux НЕ используем headless, так как Google может блокировать
                # Вместо этого используем виртуальный дисплей (Xvfb)
                # chrome_options.add_argument('--headless')  # Отключаем headless
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--window-size=1920,1080')
                # Дополнительные опции для стабильности
                chrome_options.add_argument('--disable-software-rasterizer')
                chrome_options.add_argument('--disable-background-timer-throttling')
                chrome_options.add_argument('--disable-backgrounding-occluded-windows')
                chrome_options.add_argument('--disable-renderer-backgrounding')
                # Убеждаемся, что DISPLAY установлен
                if 'DISPLAY' not in os.environ:
                    os.environ['DISPLAY'] = ':99'
            
            # Опции для обхода детекции автоматизации
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Добавляем user agent для обхода детекции
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36')
            
            # Отключаем флаги автоматизации
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-extensions')
            
            # Проверяем доступность виртуального дисплея перед инициализацией
            if sys.platform != 'win32':
                # Проверяем, что Xvfb запущен
                import subprocess
                try:
                    xvfb_check = subprocess.run(['ps', 'aux'], 
                                              capture_output=True, 
                                              text=True,
                                              timeout=2)
                    if xvfb_check.returncode == 0 and 'xvfb' not in xvfb_check.stdout.lower():
                        logger.warning("Xvfb not found, Chrome may not work properly")
                except:
                    pass
            
            # Используем webdriver-manager для автоматической установки драйвера
            try:
                driver_path = ChromeDriverManager().install()
                service = Service(driver_path)
                # Добавляем небольшую задержку перед инициализацией для стабильности
                time.sleep(0.5)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                logger.warning(f"Error with webdriver-manager: {e}, trying system ChromeDriver")
                time.sleep(0.5)
                self.driver = webdriver.Chrome(options=chrome_options)
            
            self.wait = WebDriverWait(self.driver, 30)
            
            logger.info("Selenium driver initialized successfully")
            
            # Пробуем загрузить сохраненные cookies (только если файл существует)
            # Не загружаем при первом запуске save_cookies.py
            if self.cookies_file.exists():
                try:
                    self._load_cookies()
                except Exception as e:
                    logger.warning(f"Could not load cookies (will try to login normally): {e}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Selenium driver: {e}")
            raise
    
    def _load_cookies(self):
        """Загружает сохраненные cookies Google, если они есть"""
        try:
            if self.cookies_file.exists():
                with open(self.cookies_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    # Переходим на Google, чтобы установить cookies
                    self.driver.get("https://accounts.google.com")
                    for cookie in cookies:
                        try:
                            self.driver.add_cookie(cookie)
                        except:
                            pass
                    logger.info(f"Loaded {len(cookies)} cookies from file")
        except Exception as e:
            logger.debug(f"Could not load cookies: {e}")
    
    def _save_cookies(self):
        """Сохраняет cookies Google для повторного использования"""
        try:
            cookies = self.driver.get_cookies()
            self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2)
            logger.info(f"Saved {len(cookies)} cookies to file")
        except Exception as e:
            logger.warning(f"Could not save cookies: {e}")
    
    def login(self) -> bool:
        """
        Вход в Мозаику через Google аккаунт
        (как в Fast-track боте)
        
        Returns:
            True если вход успешен, False в противном случае
        """
        try:
            from config.settings import MOSAICA_URL
            from selenium.webdriver.common.action_chains import ActionChains
            
            logger.info("Logging in to Mosaica...")
            
            # Сначала пробуем использовать сохраненные cookies
            if self.cookies_file.exists():
                try:
                    logger.info("Trying to use saved cookies...")
                    # Переходим на Мозаику
                    self.driver.get(MOSAICA_URL)
                    time.sleep(2)
                    
                    # Загружаем cookies для Мозаики
                    with open(self.cookies_file, 'r', encoding='utf-8') as f:
                        cookies = json.load(f)
                    
                    # Устанавливаем cookies для домена mosaica.ai
                    for cookie in cookies:
                        try:
                            cookie_copy = cookie.copy()
                            cookie_copy.pop('sameSite', None)
                            cookie_copy.pop('expiry', None)
                            # Устанавливаем домен, если нужно
                            if 'domain' in cookie_copy and 'mosaica.ai' not in cookie_copy.get('domain', ''):
                                cookie_copy['domain'] = '.mosaica.ai'
                            self.driver.add_cookie(cookie_copy)
                        except:
                            pass
                    
                    # Обновляем страницу
                    self.driver.refresh()
                    time.sleep(3)
                    
                    # Проверяем, авторизованы ли мы
                    current_url = self.driver.current_url
                    if "mosaica.ai" in current_url.lower() and "accounts.google.com" not in current_url.lower() and "login" not in current_url.lower():
                        logger.info("Successfully logged in using saved cookies!")
                        self._handle_chrome_signin_modal()
                        return True
                    else:
                        logger.info("Cookies didn't work, proceeding with normal login...")
                except Exception as e:
                    logger.warning(f"Could not use saved cookies: {e}, proceeding with normal login...")
            
            # Переходим на главную страницу Мозаики (не /login)
            self.driver.get(MOSAICA_URL)
            logger.info(f"Opened {MOSAICA_URL}")
            time.sleep(2)
            
            # Ищем кнопку "Please, Login"
            logger.info("Looking for 'Please, Login' button...")
            login_button_selectors = [
                (By.CSS_SELECTOR, 'a.link-over'),
                (By.XPATH, '//a[contains(text(), "Please, Login")]'),
                (By.XPATH, '//a[contains(@onclick, "login")]'),
                (By.CSS_SELECTOR, 'div.t-header-menu_item.login-tab a'),
            ]
            
            login_button = None
            for by, selector in login_button_selectors:
                try:
                    login_button = self.wait.until(EC.element_to_be_clickable((by, selector)))
                    logger.info(f"Found 'Please, Login' button using selector: {selector}")
                    break
                except:
                    continue
            
            if not login_button:
                # Проверяем, может уже авторизованы
                current_url = self.driver.current_url
                if "mosaica.ai" in current_url.lower() and "accounts.google.com" not in current_url.lower() and "login" not in current_url.lower():
                    logger.info("Already logged in!")
                    return True
                logger.error("Could not find 'Please, Login' button")
                return False
            
            # Пробуем разные способы нажатия кнопки
            clicked = False
            
            # Способ 1: Прямой вызов функции login() через JavaScript
            try:
                self.driver.execute_script("login();")
                logger.info("Called login() function via JavaScript")
                clicked = True
                time.sleep(2)
            except Exception as e:
                logger.debug(f"Could not call login() via JS: {e}")
            
            # Способ 2: JavaScript click
            if not clicked:
                try:
                    self.driver.execute_script("arguments[0].click();", login_button)
                    logger.info("Clicked 'Please, Login' button (JavaScript click)")
                    clicked = True
                    time.sleep(2)
                except Exception as e:
                    logger.debug(f"Could not click via JS: {e}")
            
            # Способ 3: Обычный click
            if not clicked:
                try:
                    login_button.click()
                    logger.info("Clicked 'Please, Login' button (normal click)")
                    clicked = True
                    time.sleep(2)
                except Exception as e:
                    logger.debug(f"Could not click normally: {e}")
            
            # Способ 4: ActionChains
            if not clicked:
                try:
                    ActionChains(self.driver).move_to_element(login_button).click().perform()
                    logger.info("Clicked 'Please, Login' button (ActionChains)")
                    clicked = True
                    time.sleep(2)
                except Exception as e:
                    logger.debug(f"Could not click via ActionChains: {e}")
            
            if not clicked:
                logger.error("Could not click 'Please, Login' button by any method")
                return False
            
            # Ждем перехода на страницу Google или автоматического входа
            logger.info("Waiting for Google login page or automatic login...")
            time.sleep(5)
            
            # Проверяем текущий URL
            current_url = self.driver.current_url
            logger.info(f"Current URL: {current_url}")
            
            # Если мы уже на mosaica.ai и не на странице Google - вход успешен (автоматический вход через сохраненную сессию)
            if "mosaica.ai" in current_url.lower() and "accounts.google.com" not in current_url.lower() and "login" not in current_url.lower():
                logger.info("Automatic login successful!")
                return True
            
            # Если мы на странице Google, вводим email и пароль
            if "accounts.google.com" in current_url.lower():
                logger.info("On Google login page, entering credentials...")
                
                # Ищем поле email
                email_selectors = [
                    (By.CSS_SELECTOR, 'input[type="email"]'),
                    (By.CSS_SELECTOR, 'input[autocomplete="username"]'),
                    (By.ID, 'identifierId'),
                ]
                
                email_field = None
                for by, selector in email_selectors:
                    try:
                        email_field = self.wait.until(EC.presence_of_element_located((by, selector)))
                        break
                    except:
                        continue
                
                if email_field:
                    if not self.email:
                        logger.error("Email is not set!")
                        return False
                    email_field.clear()
                    email_field.send_keys(self.email)
                    logger.info("Email entered")
                    time.sleep(1)
                    
                    # Ищем кнопку "Далее" или "Next"
                    next_button = None
                    try:
                        next_button = self.driver.find_element(By.XPATH, '//button[contains(., "Далее") or contains(., "Next")]')
                        next_button.click()
                        time.sleep(2)
                    except:
                        # Пробуем через Enter
                        email_field.send_keys(Keys.RETURN)
                        time.sleep(2)
                    
                    # Ищем поле пароля (с более длительным ожиданием)
                    # Google может показывать поле пароля с задержкой после ввода email
                    logger.info("Waiting for password field to appear...")
                    time.sleep(3)  # Увеличиваем время ожидания
                    
                    password_selectors = [
                        (By.CSS_SELECTOR, 'input[type="password"]'),
                        (By.CSS_SELECTOR, 'input[name="password"]'),
                        (By.CSS_SELECTOR, 'input[name="Passwd"]'),
                        (By.ID, 'password'),
                        (By.ID, 'Passwd'),
                        (By.NAME, 'password'),
                        (By.NAME, 'Passwd'),
                        (By.XPATH, '//input[@type="password"]'),
                        (By.XPATH, '//input[contains(@name, "password") or contains(@name, "Passwd")]'),
                        (By.XPATH, '//input[@autocomplete="current-password"]'),
                    ]
                    
                    password_field = None
                    # Пробуем найти поле пароля с увеличенным таймаутом
                    max_attempts = 3
                    for attempt in range(max_attempts):
                        for by, selector in password_selectors:
                            try:
                                # Увеличиваем таймаут до 15 секунд
                                password_field = WebDriverWait(self.driver, 15).until(
                                    EC.presence_of_element_located((by, selector))
                                )
                                # Проверяем, что элемент видим
                                if password_field.is_displayed():
                                    logger.info(f"Found password field using selector: {selector} (attempt {attempt + 1})")
                                    break
                            except Exception as e:
                                logger.debug(f"Password field not found with selector {selector} (attempt {attempt + 1}): {e}")
                                continue
                        
                        if password_field:
                            break
                        
                        if attempt < max_attempts - 1:
                            logger.info(f"Password field not found, waiting 3 more seconds (attempt {attempt + 1}/{max_attempts})...")
                            time.sleep(3)
                    
                    # Если все еще не найдено, пробуем через JavaScript
                    if not password_field:
                        logger.info("Trying to find password field via JavaScript...")
                        try:
                            password_field = self.driver.execute_script("""
                                var inputs = document.querySelectorAll('input[type="password"]');
                                for (var i = 0; i < inputs.length; i++) {
                                    if (inputs[i].offsetParent !== null) {
                                        return inputs[i];
                                    }
                                }
                                return null;
                            """)
                            if password_field:
                                logger.info("Found password field via JavaScript")
                        except:
                            pass
                    
                    if not password_field:
                        logger.error("Password field not found after waiting")
                        # Пробуем найти все input элементы для отладки
                        try:
                            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                            logger.debug(f"Found {len(all_inputs)} input elements on page")
                            for inp in all_inputs[:5]:  # Показываем только первые 5
                                try:
                                    inp_type = inp.get_attribute("type")
                                    inp_name = inp.get_attribute("name")
                                    inp_id = inp.get_attribute("id")
                                    logger.debug(f"Input: type={inp_type}, name={inp_name}, id={inp_id}")
                                except:
                                    pass
                        except:
                            pass
                        return False
                    
                    if not self.password:
                        logger.error("Password is not set!")
                        return False
                    
                    # Прокручиваем к элементу
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", password_field)
                        time.sleep(0.5)
                    except:
                        pass
                    
                    # Пробуем очистить и ввести пароль
                    try:
                        password_field.clear()
                    except:
                        # Если clear не работает, используем JavaScript
                        self.driver.execute_script("arguments[0].value = '';", password_field)
                    
                    # Вводим пароль
                    try:
                        password_field.send_keys(self.password)
                        logger.info("Password entered via send_keys")
                    except Exception as e:
                        logger.warning(f"send_keys failed: {e}, trying JavaScript")
                        # Если обычный ввод не работает, используем JavaScript
                        self.driver.execute_script("arguments[0].value = arguments[1];", password_field, self.password)
                        # Триггерим события для активации валидации
                        self.driver.execute_script("""
                            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                        """, password_field)
                        logger.info("Password entered via JavaScript")
                    
                    time.sleep(1)
                    
                    # Ищем кнопку "Далее" или "Next" для пароля
                    try:
                        next_button = self.wait.until(
                            EC.element_to_be_clickable((By.XPATH, '//button[contains(., "Далее") or contains(., "Next")]'))
                        )
                        # Прокручиваем к кнопке
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                        time.sleep(0.5)
                        next_button.click()
                        logger.info("Clicked Next button")
                    except Exception as e:
                        logger.warning(f"Next button not found: {e}, trying Enter")
                        # Если кнопка не найдена, пробуем Enter
                        try:
                            password_field.send_keys(Keys.RETURN)
                            logger.info("Pressed Enter")
                        except:
                            # Если и это не работает, используем JavaScript
                            self.driver.execute_script("arguments[0].form.submit();", password_field)
                            logger.info("Submitted form via JavaScript")
                    
                    time.sleep(5)
                    
                    # Проверяем текущий URL и обрабатываем разные сценарии
                    current_url = self.driver.current_url
                    logger.info(f"Current URL after password: {current_url[:100]}...")
                    
                    # Обрабатываем challenge страницу (если Google требует дополнительную проверку)
                    max_redirect_attempts = 5
                    for attempt in range(max_redirect_attempts):
                        current_url = self.driver.current_url
                        logger.info(f"Redirect attempt {attempt + 1}/{max_redirect_attempts}, URL: {current_url[:100]}...")
                        
                        # Если мы на странице Мозаики - успех!
                        if "mosaica.ai" in current_url.lower() and "accounts.google.com" not in current_url.lower():
                            logger.info("Login successful!")
                            # Сохраняем cookies для следующего раза
                            self._save_cookies()
                            # Обрабатываем модальное окно Chrome "Войти в Chrome?" если оно появилось
                            self._handle_chrome_signin_modal()
                            return True
                        
                        # Если на странице согласия (consent)
                        if "consent" in current_url.lower():
                            logger.info("Google consent page detected, looking for Allow/Разрешить button...")
                            try:
                                # Ищем кнопку "Разрешить" или "Allow"
                                consent_button_selectors = [
                                    (By.XPATH, '//button[contains(., "Разрешить") or contains(., "Allow")]'),
                                    (By.XPATH, '//button[contains(., "Продолжить") or contains(., "Continue")]'),
                                    (By.ID, 'submit_approve_access'),
                                    (By.CSS_SELECTOR, 'button[type="submit"]'),
                                    (By.XPATH, '//div[@role="button" and (contains(., "Разрешить") or contains(., "Allow"))]'),
                                ]
                                
                                for by, selector in consent_button_selectors:
                                    try:
                                        consent_button = WebDriverWait(self.driver, 5).until(
                                            EC.element_to_be_clickable((by, selector))
                                        )
                                        if consent_button and consent_button.is_displayed():
                                            logger.info(f"Found consent button: {selector}, clicking...")
                                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", consent_button)
                                            time.sleep(0.5)
                                            self.driver.execute_script("arguments[0].click();", consent_button)
                                            logger.info("Clicked consent button")
                                            time.sleep(5)
                                            break
                                    except:
                                        continue
                            except Exception as e:
                                logger.warning(f"Error handling consent page: {e}")
                        
                        # Если на странице challenge (дополнительная проверка)
                        elif "challenge" in current_url.lower():
                            logger.warning("Google challenge page detected - may require 2FA or additional verification")
                            # Пробуем найти и обработать challenge
                            try:
                                # Ищем кнопки "Попробовать другой способ" или "Try another way"
                                challenge_selectors = [
                                    (By.XPATH, '//button[contains(., "Попробовать другой способ") or contains(., "Try another way")]'),
                                    (By.XPATH, '//a[contains(., "Попробовать другой способ") or contains(., "Try another way")]'),
                                ]
                                
                                for by, selector in challenge_selectors:
                                    try:
                                        challenge_link = self.driver.find_element(by, selector)
                                        if challenge_link.is_displayed():
                                            logger.info("Found 'Try another way' link, clicking...")
                                            self.driver.execute_script("arguments[0].click();", challenge_link)
                                            time.sleep(3)
                                            break
                                    except:
                                        continue
                            except Exception as e:
                                logger.warning(f"Error handling challenge page: {e}")
                            
                            # Если challenge требует ввода кода или другого действия, это проблема
                            logger.error("Google requires additional verification (2FA/challenge) - cannot proceed automatically")
                            return False
                        
                        # Ждем редирект
                        time.sleep(5)
                    
                    # Если после всех попыток все еще на Google
                    current_url = self.driver.current_url
                    logger.warning(f"Still on Google page after {max_redirect_attempts} attempts: {current_url[:200]}")
                    return False
                
                logger.error("Could not complete Google login - password field not found or login failed")
                return False
            
            # Если мы все еще на главной странице, возможно нужно подождать
            time.sleep(3)
            current_url = self.driver.current_url
            if "mosaica.ai" in current_url.lower() and "accounts.google.com" not in current_url.lower() and "login" not in current_url.lower():
                logger.info("Login successful!")
                # Сохраняем cookies для следующего раза
                self._save_cookies()
                # Обрабатываем модальное окно Chrome "Войти в Chrome?" если оно появилось
                self._handle_chrome_signin_modal()
                return True
            
            logger.error("Login failed - still on login page")
            return False
                
        except Exception as e:
            logger.error(f"Error during login: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _handle_chrome_signin_modal(self):
        """
        Обрабатывает модальное окно Chrome "Войти в Chrome?" которое может появиться после логина.
        Закрывает окно или нажимает "Использовать Chrome, не входя в аккаунт".
        Основано на методе close_chrome_signin_dialog из Fast-track бота.
        """
        try:
            # Ждем немного, чтобы модальное окно успело появиться
            time.sleep(2)
            
            # Сначала проверяем, есть ли вообще диалог "Войти в Chrome?"
            try:
                dialog_title = self.driver.find_elements(By.XPATH, '//*[contains(text(), "Войти в Chrome") or contains(text(), "Sign in to Chrome")]')
                if not dialog_title:
                    logger.debug("Chrome sign-in modal not found")
                    return False  # Диалог не найден
            except:
                pass
            
            # Ищем кнопку "Продолжить как..." или "Использовать Chrome, не входя в аккаунт"
            chrome_button_selectors = [
                # Приоритетные - точные совпадения
                (By.XPATH, '//button[contains(text(), "Продолжить как")]'),
                (By.XPATH, '//button[contains(text(), "Continue as")]'),
                (By.XPATH, '//button[contains(text(), "Использовать Chrome, не входя в аккаунт")]'),
                (By.XPATH, '//button[contains(text(), "Use Chrome, not signed in")]'),
                # Альтернативные - частичные совпадения
                (By.XPATH, '//button[contains(., "Продолжить")]'),
                (By.XPATH, '//button[contains(., "Continue")]'),
                # По классу или роли
                (By.XPATH, '//div[@role="dialog"]//button[contains(@class, "VfPpkd")]'),
                (By.XPATH, '//div[contains(@class, "dialog")]//button[contains(text(), "Продолжить")]'),
            ]
            
            for by, selector in chrome_button_selectors:
                try:
                    # Используем короткий таймаут для быстрой проверки
                    button = WebDriverWait(self.driver, 1).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if button and button.is_displayed():
                        logger.info("Found Chrome sign-in modal, closing...")
                        # Пробуем несколько способов нажатия
                        try:
                            self.driver.execute_script("arguments[0].click();", button)
                        except:
                            try:
                                button.click()
                            except:
                                # Пробуем через ActionChains
                                ActionChains(self.driver).move_to_element(button).click().perform()
                        time.sleep(0.5)
                        logger.info("Chrome sign-in modal closed")
                        return True
                except:
                    continue
            
            # Альтернативный способ: пробуем нажать Escape
            try:
                from selenium.webdriver.common.keys import Keys
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                logger.info("Pressed Escape to close Chrome sign-in modal")
                time.sleep(1)
                return True
            except:
                pass
            
            logger.debug("Chrome sign-in modal not found or could not be closed")
            return False
            
        except Exception as e:
            logger.debug(f"Error handling Chrome sign-in modal: {e}")
            return False
    
    def _clean_stats_text(self, stats_text: str) -> str:
        """
        Очищает текст статистики от шапки и яндекс ссылок.
        
        Args:
            stats_text: Исходный текст статистики из textarea
            
        Returns:
            Очищенный текст статистики
        """
        if not stats_text:
            return stats_text
        
        lines = stats_text.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            # Пропускаем первую строку (шапку с заголовками)
            if i == 0:
                # Проверяем, является ли это шапкой (содержит разделители типа "_; Name; Brand; Article; Gender; Image2; Ext Images; Color; Category: Description; tags; links")
                if '_;' in line or 'Name;' in line or 'Brand;' in line or 'Article;' in line:
                    continue
            
            # Пропускаем строки с яндекс ссылками
            if 'disk.yandex.ru' in line or 'https://disk.yandex.ru' in line:
                continue
            
            # Добавляем остальные строки
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    def navigate_to_showoff_collections(self) -> bool:
        """
        Переход в раздел Showoff Collections через вызов JavaScript функции view_custom_collections()
        """
        try:
            logger.info("Navigating to Showoff Collections...")
            
            # Ждем полной загрузки страницы
            self.wait.until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            time.sleep(5)  # Дополнительное ожидание для загрузки JavaScript
            
            # Пробуем вызвать функцию view_custom_collections()
            function_exists = False
            for attempt in range(30):
                try:
                    function_exists = (
                        self.driver.execute_script("return typeof view_custom_collections === 'function';") or
                        self.driver.execute_script("return typeof window.view_custom_collections === 'function';")
                    )
                    if function_exists:
                        logger.info(f"Function found after {attempt + 1} attempts")
                        break
                    time.sleep(1)
                except:
                    time.sleep(1)
            
            if function_exists:
                self.driver.execute_script("view_custom_collections();")
                logger.info("Function view_custom_collections() called")
                time.sleep(5)
                
                # Проверяем, что мы на правильной странице
                current_url = self.driver.current_url
                if "mosaica.ai" in current_url.lower() and "accounts.google.com" not in current_url.lower():
                    logger.info("Successfully navigated to Showoff Collections")
                    return True
            else:
                logger.warning("Function view_custom_collections not found, trying alternative methods...")
                # Альтернативный способ - через hash
                try:
                    self.driver.execute_script("window.location.hash = '#/collections';")
                    time.sleep(3)
                    return True
                except:
                    pass
            
            return False
        except Exception as e:
            logger.error(f"Error navigating to Showoff Collections: {e}")
            return False
    
    def search_collection_by_id(self, collection_id: str) -> bool:
        """
        Ищет коллекцию по ID в поле поиска
        
        Args:
            collection_id: ID коллекции для поиска
        
        Returns:
            True если коллекция найдена, False в противном случае
        """
        try:
            logger.info(f"Searching for collection by ID: {collection_id}...")
            
            # Ищем поле поиска
            search_selectors = [
                (By.ID, "so_search_coll_name"),
                (By.XPATH, '//input[@id="so_search_coll_name"]'),
                (By.CSS_SELECTOR, 'input#so_search_coll_name'),
            ]
            
            search_field = None
            for by, selector in search_selectors:
                try:
                    search_field = self.wait.until(EC.presence_of_element_located((by, selector)))
                    logger.info(f"Found search field using selector: {selector}")
                    break
                except:
                    continue
            
            if not search_field:
                # Пробуем через JavaScript
                try:
                    search_field = self.driver.execute_script("return document.getElementById('so_search_coll_name');")
                    if not search_field:
                        logger.error("Could not find search field")
                        return False
                except:
                    return False
            
            # Прокручиваем к полю поиска
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", search_field)
                time.sleep(0.5)
            except:
                pass
            
            # Вводим ID в поле поиска
            try:
                # Очищаем поле несколько раз для надежности
                for _ in range(3):
                    try:
                        search_field.clear()
                        time.sleep(0.2)
                    except:
                        pass
                
                # Пробуем кликнуть и сфокусироваться
                try:
                    search_field.click()
                    time.sleep(0.3)
                except:
                    try:
                        self.driver.execute_script("arguments[0].focus(); arguments[0].click();", search_field)
                        time.sleep(0.3)
                    except:
                        pass
                
                # Вводим ID через Selenium
                try:
                    search_field.send_keys(collection_id)
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"Error sending keys: {e}")
                
                # Проверяем, что текст введен
                entered_value = search_field.get_attribute("value")
                logger.info(f"Value in search field after send_keys: '{entered_value}'")
                
                # Если текст не введен или не полностью, используем JavaScript
                if not entered_value or entered_value != collection_id:
                    logger.info("Text not entered correctly, trying JavaScript method...")
                    self.driver.execute_script("""
                        var field = arguments[0];
                        var value = arguments[1];
                        field.value = '';
                        field.value = value;
                        field.dispatchEvent(new Event('input', { bubbles: true }));
                        field.dispatchEvent(new Event('keyup', { bubbles: true }));
                        field.dispatchEvent(new Event('change', { bubbles: true }));
                        field.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true }));
                        field.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
                    """, search_field, collection_id)
                    time.sleep(1)
                    
                    # Проверяем еще раз
                    entered_value = search_field.get_attribute("value")
                    logger.info(f"Value in search field after JavaScript: '{entered_value}'")
                
                # Дополнительно триггерим события для фильтрации
                self.driver.execute_script("""
                    var field = arguments[0];
                    field.dispatchEvent(new Event('input', { bubbles: true }));
                    field.dispatchEvent(new Event('keyup', { bubbles: true }));
                    field.dispatchEvent(new Event('change', { bubbles: true }));
                    // Пробуем вызвать функцию фильтрации, если она есть
                    if (typeof so_filter_collections === 'function') {
                        so_filter_collections();
                    }
                """, search_field)
                
                # Ждем результатов поиска (увеличено время ожидания)
                logger.info("Waiting for search results to appear...")
                time.sleep(3)  # Увеличено с 2 до 3 секунд
                
                # Проверяем, что значение все еще в поле
                final_value = search_field.get_attribute("value")
                if final_value == collection_id:
                    logger.info(f"Collection ID successfully entered: {collection_id}")
                    return True
                else:
                    logger.warning(f"Collection ID may not be entered correctly. Expected: '{collection_id}', Got: '{final_value}'")
                    # Все равно продолжаем, может быть работает
                    return True
                    
            except Exception as e:
                logger.error(f"Error entering collection ID: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False
                
        except Exception as e:
            logger.error(f"Error searching for collection: {e}")
            return False
    
    def click_collection(self, collection_id: str = None) -> bool:
        """
        Кликает на первую видимую коллекцию в списке (после поиска)
        
        Returns:
            True если успешно, False в противном случае
        """
        try:
            logger.info("Clicking on collection...")
            
            # Ждем появления коллекций в списке
            logger.info("Waiting for collections to appear in list...")
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.XPATH, '//li[contains(@class, "js_select_coll_li")]'))
                )
                time.sleep(1)  # Дополнительное ожидание для полной загрузки
            except:
                logger.warning("Collections may not be visible yet, continuing anyway...")
            
            # Ищем видимые коллекции в списке
            collection_selectors = [
                (By.XPATH, '//li[contains(@class, "custom-collection_item") and contains(@class, "js_select_coll_li")]'),
                (By.XPATH, '//li[contains(@class, "js_select_coll_li")]'),
                (By.XPATH, '//li[contains(@class, "custom-collection_item")]'),
                (By.XPATH, '//li[contains(@class, "collection-items__item")]'),
            ]
            
            collection_element = None
            collection_id_attr = None
            
            # Получаем collection_id из параметра или из атрибута класса
            target_collection_id = collection_id or getattr(self, '_current_collection_id', None)
            
            # Сначала пробуем найти коллекцию по data-id атрибуту (как в Fast-track)
            try:
                if target_collection_id:
                    # Ищем все элементы с data-id, которые содержат наш collection_id
                    all_elements = self.driver.find_elements(By.XPATH, f'//li[@data-id="{target_collection_id}"]')
                    if not all_elements:
                        # Пробуем без точного совпадения
                        all_elements = self.driver.find_elements(By.XPATH, f'//li[contains(@data-id, "{target_collection_id[:8]}")]')
                else:
                    all_elements = []
                
                for elem in all_elements:
                    try:
                        # Проверяем видимость через JavaScript (более надежно)
                        is_visible = self.driver.execute_script("""
                            var elem = arguments[0];
                            var style = window.getComputedStyle(elem);
                            return style.display !== 'none' && style.visibility !== 'hidden' && elem.offsetParent !== null;
                        """, elem)
                        
                        if is_visible:
                            collection_id_attr = elem.get_attribute("data-id")
                            collection_element = elem
                            logger.info(f"Found collection by data-id: {collection_id_attr}")
                            break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Error finding by data-id: {e}")
            
            # Если не нашли по data-id, ищем по селекторам
            if not collection_element:
                for by, selector in collection_selectors:
                    try:
                        elements = self.driver.find_elements(by, selector)
                        logger.info(f"Found {len(elements)} elements with selector: {selector}")
                        for elem in elements:
                            try:
                                # Проверяем видимость через JavaScript
                                is_visible = self.driver.execute_script("""
                                    var elem = arguments[0];
                                    var style = window.getComputedStyle(elem);
                                    return style.display !== 'none' && style.visibility !== 'hidden' && elem.offsetParent !== null;
                                """, elem)
                                
                                if is_visible:
                                    # Пробуем получить ID коллекции из data-id атрибута
                                    try:
                                        collection_id_attr = elem.get_attribute("data-id")
                                        if collection_id_attr:
                                            logger.info(f"Found collection with data-id: {collection_id_attr}")
                                    except:
                                        pass
                                    
                                    collection_element = elem
                                    logger.info(f"Found visible collection element")
                                    break
                            except:
                                continue
                        if collection_element:
                            break
                    except Exception as e:
                        logger.debug(f"Error with selector {selector}: {e}")
                        continue
            
            # Если нашли элемент, но нет data-id, пробуем получить его из других атрибутов
            if collection_element and not collection_id_attr:
                try:
                    collection_id_attr = collection_element.get_attribute("data-id") or collection_element.get_attribute("id")
                except:
                    pass
            
            # Если нашли collection_id_attr, пробуем использовать so_draw_blocks (как в Fast-track)
            if collection_id_attr:
                try:
                    logger.info(f"Trying to open collection via so_draw_blocks with ID: {collection_id_attr}")
                    self.driver.execute_script(f'so_draw_blocks("draw_collection_items", "{collection_id_attr}");')
                    time.sleep(2)
                    logger.info("Collection opened via so_draw_blocks")
                    return True
                except Exception as e:
                    logger.warning(f"Could not use so_draw_blocks: {e}, trying click instead...")
            
            # Если не нашли элемент, но есть target_collection_id, пробуем использовать его напрямую
            if not collection_element and target_collection_id:
                try:
                    logger.info(f"Trying to open collection directly via so_draw_blocks with ID: {target_collection_id}")
                    self.driver.execute_script(f'so_draw_blocks("draw_collection_items", "{target_collection_id}");')
                    time.sleep(2)
                    logger.info("Collection opened via so_draw_blocks (direct)")
                    return True
                except Exception as e:
                    logger.warning(f"Could not use so_draw_blocks directly: {e}")
            
            if not collection_element:
                logger.error("Could not find collection element")
                # Выводим отладочную информацию
                try:
                    all_li = self.driver.find_elements(By.TAG_NAME, "li")
                    logger.info(f"Total <li> elements on page: {len(all_li)}")
                    visible_li = [li for li in all_li if self.driver.execute_script("""
                        var elem = arguments[0];
                        var style = window.getComputedStyle(elem);
                        return style.display !== 'none' && style.visibility !== 'hidden' && elem.offsetParent !== null;
                    """, li)]
                    logger.info(f"Visible <li> elements: {len(visible_li)}")
                    
                    # Пробуем найти по тексту или другим атрибутам
                    logger.info("Trying to find collection by searching in visible elements...")
                    for li in visible_li[:10]:  # Проверяем первые 10 видимых
                        try:
                            text = li.text
                            data_id = li.get_attribute("data-id")
                            logger.debug(f"Element text: {text[:50]}, data-id: {data_id}")
                        except:
                            pass
                except:
                    pass
                return False
            
            # Прокручиваем к коллекции
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", collection_element)
                time.sleep(0.5)
            except:
                pass
            
            # Пробуем кликнуть на span внутри li (как в Fast-track боте)
            try:
                span_element = collection_element.find_element(By.XPATH, './/span[contains(@class, "custom-collection_item-text")]')
                is_visible = self.driver.execute_script("""
                    var elem = arguments[0];
                    var style = window.getComputedStyle(elem);
                    return style.display !== 'none' && style.visibility !== 'hidden' && elem.offsetParent !== null;
                """, span_element)
                
                if is_visible:
                    self.driver.execute_script("arguments[0].click();", span_element)
                    logger.info("Collection clicked via span element")
                    time.sleep(2)
                    return True
            except:
                pass
            
            # Если span не найден, кликаем на сам элемент
            try:
                self.driver.execute_script("arguments[0].click();", collection_element)
                logger.info("Collection clicked via JavaScript")
                time.sleep(2)
                return True
            except Exception as e:
                logger.error(f"Error clicking collection: {e}")
                return False
        except Exception as e:
            logger.error(f"Error in click_collection: {e}")
            return False
    
    def get_collection_report(self, collection_id: str) -> Optional[Dict]:
        """
        Собирает отчет по коллекции из Мозаики
        Логика: переход в Showoff -> поиск по ID -> 
        открыть редактирование -> получить статистику
        
        Args:
            collection_id: ID коллекции
        
        Returns:
            Словарь с данными отчета или None
        """
        try:
            # 1. Переходим в Showoff Collections
            if not self.navigate_to_showoff_collections():
                logger.error("Failed to navigate to Showoff Collections")
                return None
            
            # 2. Ищем коллекцию по ID
            if not self.search_collection_by_id(collection_id):
                logger.error(f"Failed to search for collection {collection_id}")
                return None
            
            time.sleep(2)  # Ждем результатов поиска
            
            # 3. Находим коллекцию в списке и нажимаем на кнопку редактирования (иконка карандаша)
            # ВАЖНО: НЕ кликаем на коллекцию, а только на кнопку редактирования!
            stats_text = None
            try:
                # Ищем коллекцию в списке по data-id
                collection_li = None
                try:
                    collection_li = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, f'//li[@data-id="{collection_id}"]'))
                    )
                    logger.info(f"Found collection in list with data-id: {collection_id}")
                except:
                    logger.warning(f"Could not find collection by exact data-id, trying alternative...")
                    # Пробуем найти по части ID
                    try:
                        collection_li = self.wait.until(
                            EC.presence_of_element_located((By.XPATH, f'//li[contains(@data-id, "{collection_id[:8]}")]'))
                        )
                        logger.info(f"Found collection by partial data-id")
                    except:
                        logger.error("Could not find collection in list")
                        return None
                
                if collection_li:
                    # Ищем кнопку редактирования (иконка карандаша) внутри этого li
                    edit_button = None
                    edit_button_id = f"so_coll_edit_button_{collection_id}"
                    
                    # Пробуем найти по ID
                    try:
                        edit_button = collection_li.find_element(By.ID, edit_button_id)
                        logger.info(f"Found edit button by ID: {edit_button_id}")
                    except:
                        # Пробуем другие селекторы
                        edit_button_selectors = [
                            (By.XPATH, f'.//button[@id="{edit_button_id}"]'),
                            (By.XPATH, './/button[contains(@id, "so_coll_edit_button")]'),
                            (By.XPATH, './/button[contains(@class, "edit")]'),
                            (By.CSS_SELECTOR, 'button[id*="edit"]'),
                        ]
                        
                        for by, selector in edit_button_selectors:
                            try:
                                edit_button = collection_li.find_element(by, selector)
                                logger.info(f"Found edit button using selector: {selector}")
                                break
                            except:
                                continue
                    
                    if edit_button:
                        # Прокручиваем к кнопке
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", edit_button)
                        time.sleep(0.5)
                        
                        # Кликаем на кнопку редактирования
                        try:
                            edit_button.click()
                            logger.info("Edit button clicked")
                        except:
                            self.driver.execute_script("arguments[0].click();", edit_button)
                            logger.info("Edit button clicked via JavaScript")
                        
                        time.sleep(2)  # Ждем открытия формы редактирования
                    else:
                        logger.warning("Could not find edit button in collection item")
                        # Пробуем открыть форму редактирования через JavaScript
                        self.driver.execute_script("""
                            if (typeof $('#so_collection_edit').length !== 'undefined' && $('#so_collection_edit').length > 0) {
                                $('#so_collection_edit').addClass('is-active');
                                $('.js_custom_collection').addClass('has-edition');
                                $('.js_select_coll_li').addClass('is-edited');
                            }
                        """)
                        time.sleep(2)
                else:
                    logger.error("Could not find collection in list")
                    return None
                
                # 4. Теперь ищем textarea с id="so_coll_stat" (поле Stat) и получаем статистику
                try:
                    stat_textarea = self.wait.until(
                        EC.presence_of_element_located((By.ID, "so_coll_stat"))
                    )
                    stats_text = stat_textarea.get_attribute("value") or stat_textarea.text
                    # Очищаем от шапки и яндекс ссылок
                    if stats_text:
                        stats_text = self._clean_stats_text(stats_text)
                    logger.info(f"Found stats text: {stats_text[:100] if stats_text else 'None'}...")
                except Exception as e:
                    logger.error(f"Could not find stats textarea (so_coll_stat): {e}")
                    # Пробуем найти через XPath
                    try:
                        stat_textarea = self.driver.find_element(By.XPATH, '//textarea[@id="so_coll_stat"]')
                        stats_text = stat_textarea.get_attribute("value") or stat_textarea.text
                        # Очищаем от шапки и яндекс ссылок
                        if stats_text:
                            stats_text = self._clean_stats_text(stats_text)
                        logger.info(f"Found stats text via XPath: {stats_text[:100] if stats_text else 'None'}...")
                    except:
                        logger.error("Could not find stats textarea by any method")
                        return None
            except Exception as e:
                logger.error(f"Error getting stats: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
            
            # 5. Статистика собрана, сразу закрываем браузер
            logger.info("Stats collected, closing browser...")
            self.close()
            
            # 6. Формируем ссылку на коллекцию из ID (ID уже есть, браузер не нужен)
            collection_link = f"https://admin.dresscode.ai/collection/{collection_id}"
            logger.info(f"Generated collection link: {collection_link}")
            
            # 7. Парсим статистику из текста
            report_data = {
                'collection_id': collection_id,
                'collection_url': collection_link,
                'stats_text': stats_text,
                'total_done': None,
                'combo_items': None,
                'total_done_items': None,
            }
            
            if stats_text:
                # Парсим данные из текста статистики
                try:
                    import re
                    
                    # Паттерн 1: "X total done items" (например, "423 total done items")
                    total_done_match = re.search(r'(\d+)\s+total\s+done\s+items?', stats_text, re.IGNORECASE)
                    if total_done_match:
                        report_data['total_done'] = int(total_done_match.group(1))
                    
                    # Паттерн 2: "X combinations done" (например, "316 combinations done")
                    combo_match = re.search(r'(\d+)\s+combinations?\s+done', stats_text, re.IGNORECASE)
                    if combo_match:
                        report_data['combo_items'] = int(combo_match.group(1))
                    
                    # Паттерн 3: "X total done" (без слова items)
                    if not report_data['total_done']:
                        total_done_match2 = re.search(r'(\d+)\s+total\s+done(?!\s+items)', stats_text, re.IGNORECASE)
                        if total_done_match2:
                            report_data['total_done'] = int(total_done_match2.group(1))
                    
                    # Паттерн 4: "Общее количество уникальных done-айтемов - X" или "– X"
                    if not report_data['total_done']:
                        total_done_pattern = re.search(r'Общее\s+количество\s+уникальных\s+done-айтемов\s*[–-]\s*(\d+)', stats_text, re.IGNORECASE)
                        if total_done_pattern:
                            report_data['total_done'] = int(total_done_pattern.group(1))
                    
                    # Паттерн 5: "Из них combo-айтемов – X"
                    if not report_data['combo_items']:
                        combo_pattern = re.search(r'Из\s+них\s+combo-айтемов\s*[–-]\s*(\d+)', stats_text, re.IGNORECASE)
                        if combo_pattern:
                            report_data['combo_items'] = int(combo_pattern.group(1))
                    
                    # Паттерн 6: "Итого total done - X айтемов" (если есть, используем, но обычно считаем сами)
                    total_match = re.search(r'Итого\s+total\s+done\s*[-–]\s*(\d+)', stats_text, re.IGNORECASE)
                    if total_match:
                        report_data['total_done_items'] = int(total_match.group(1))
                    
                    # Если не нашли total_done_items, рассчитываем: total_done + combo_items
                    if report_data['total_done'] and report_data['combo_items']:
                        report_data['total_done_items'] = report_data['total_done'] + report_data['combo_items']
                    
                except Exception as e:
                    logger.warning(f"Error parsing stats: {e}")
            
            logger.info(f"Report collected successfully. Stats: {stats_text[:100] if stats_text else 'None'}, Link: {collection_link}")
            return report_data
            
        except Exception as e:
            logger.error(f"Error collecting report: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def close(self):
        """Закрытие браузера и всех связанных процессов"""
        if self.driver:
            try:
                # Закрываем все окна браузера
                try:
                    self.driver.close()
                except:
                    pass
                
                # Завершаем драйвер
                try:
                    self.driver.quit()
                except:
                    pass
                
                self.driver = None  # Помечаем как закрытый
                logger.info("Browser closed")
                
                # Дополнительно: принудительно убиваем процессы Chrome
                # Это важно, так как иногда driver.quit() не убивает все процессы
                try:
                    import subprocess
                    import time
                    time.sleep(1)  # Даем время на закрытие
                    
                    # Убиваем процессы Chrome более агрессивно
                    # Пробуем разные способы для надежности
                    try:
                        # Способ 1: pkill по имени процесса
                        subprocess.run(['pkill', '-9', '-f', 'chrome'], 
                                     capture_output=True, 
                                     timeout=3,
                                     check=False)
                    except:
                        pass
                    
                    try:
                        # Способ 2: killall (если доступен)
                        subprocess.run(['killall', '-9', 'chrome'], 
                                     capture_output=True, 
                                     timeout=3,
                                     check=False)
                    except:
                        pass
                    
                    try:
                        # Способ 3: через ps и kill
                        result = subprocess.run(['ps', 'aux'], 
                                              capture_output=True, 
                                              text=True,
                                              timeout=3)
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if 'chrome' in line.lower() and 'grep' not in line.lower():
                                    parts = line.split()
                                    if len(parts) > 1:
                                        pid = parts[1]
                                        try:
                                            subprocess.run(['kill', '-9', pid], 
                                                         capture_output=True, 
                                                         timeout=2,
                                                         check=False)
                                        except:
                                            pass
                    except:
                        pass
                        
                except Exception as e:
                    logger.debug(f"Could not kill Chrome processes: {e}")
                    
            except Exception as e:
                # Браузер уже может быть закрыт
                logger.debug(f"Browser already closed or error closing: {e}")
                self.driver = None
                # Пробуем принудительно убить процессы Chrome
                try:
                    import subprocess
                    subprocess.run(['pkill', '-9', '-f', 'chrome'], 
                                 capture_output=True, 
                                 timeout=3,
                                 check=False)
                except:
                    pass

