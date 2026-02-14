import sqlite3
import os
from typing import Optional

DB_NAME = "trading_bot.db"


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Создание таблиц в базе данных"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                language TEXT DEFAULT 'ru',
                is_active INTEGER DEFAULT 0,
                activated_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Добавляем колонку language, если ее нет (для уже существующих баз)
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
            self.conn.commit()
        except Exception:
            # Колонка уже существует
            pass
        
        # Создаем таблицу signal_feedback
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                pair TEXT,
                signal_type TEXT,
                feedback TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Добавляем колонку is_banned, если ее нет
        try:
            self.cursor.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
            self.conn.commit()
        except Exception:
            # Колонка уже существует
            pass
        
        self.conn.commit()

    def add_user(self, user_id: int, username: Optional[str] = None, full_name: Optional[str] = None):
        """Добавление нового пользователя"""
        try:
            self.cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, full_name)
                VALUES (?, ?, ?)
            """, (user_id, username, full_name))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении пользователя: {e}")
            return False

    def activate_user(self, user_id: int):
        """Активация пользователя после ввода кода"""
        try:
            self.cursor.execute("""
                UPDATE users 
                SET is_active = 1, activated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при активации пользователя: {e}")
            return False

    def is_user_active(self, user_id: int) -> bool:
        """Проверка активности пользователя"""
        self.cursor.execute("SELECT is_active FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        return result[0] == 1 if result else False

    def user_exists(self, user_id: int) -> bool:
        """Проверка существования пользователя"""
        self.cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone() is not None

    def set_language(self, user_id: int, language: str):
        """Сохранение языка пользователя"""
        try:
            self.cursor.execute("""
                UPDATE users SET language = ? WHERE user_id = ?
            """, (language, user_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при сохранении языка: {e}")
            return False

    def get_language(self, user_id: int) -> str:
        """Получение языка пользователя"""
        self.cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result and result[0] else None

    def add_feedback(self, user_id: int, pair: str, signal_type: str, feedback: str):
        """Добавление фидбека по сигналу"""
        try:
            self.cursor.execute("""
                INSERT INTO signal_feedback (user_id, pair, signal_type, feedback)
                VALUES (?, ?, ?, ?)
            """, (user_id, pair, signal_type, feedback))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении фидбека: {e}")
            return False

    def get_feedback_stats(self) -> dict:
        """Получение статистики по фидбеку сигналов"""
        try:
            # Общая статистика
            self.cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN feedback = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN feedback = 'fail' THEN 1 ELSE 0 END) as failed
                FROM signal_feedback
            """)
            total_stats = self.cursor.fetchone()

            # Статистика за сегодня
            self.cursor.execute("""
                SELECT
                    COUNT(*) as total_today,
                    SUM(CASE WHEN feedback = 'success' THEN 1 ELSE 0 END) as successful_today,
                    SUM(CASE WHEN feedback = 'fail' THEN 1 ELSE 0 END) as failed_today
                FROM signal_feedback
                WHERE DATE(created_at) = DATE('now')
            """)
            today_stats = self.cursor.fetchone()

            return {
                'total_signals': total_stats[0] or 0,
                'successful': total_stats[1] or 0,
                'failed': total_stats[2] or 0,
                'total_today': today_stats[0] or 0,
                'successful_today': today_stats[1] or 0,
                'failed_today': today_stats[2] or 0
            }
        except Exception as e:
            print(f"Ошибка при получении статистики: {e}")
            return {
                'total_signals': 0,
                'successful': 0,
                'failed': 0,
                'total_today': 0,
                'successful_today': 0,
                'failed_today': 0
            }

    def get_all_users(self) -> list:
        """Получение списка ID всех пользователей"""
        try:
            self.cursor.execute("SELECT user_id FROM users")
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Ошибка при получении всех пользователей: {e}")
            return []

    def get_users_stats(self) -> dict:
        """Получение статистики пользователей"""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM users")
            total_users = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
            active_users = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
            banned_users = self.cursor.fetchone()[0]

            # Пользователи за последние 24 часа
            self.cursor.execute("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')")
            new_users_24h = self.cursor.fetchone()[0]

            return {
                "total": total_users,
                "active": active_users,
                "banned": banned_users,
                "new_24h": new_users_24h
            }
        except Exception as e:
            print(f"Ошибка при получении статистики пользователей: {e}")
            return {"total": 0, "active": 0, "banned": 0, "new_24h": 0}

    def ban_user(self, user_id: int):
        """Заблокировать пользователя"""
        try:
            self.cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при блокировке пользователя: {e}")
            return False

    def unban_user(self, user_id: int):
        """Разблокировать пользователя"""
        try:
            self.cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при разблокировке пользователя: {e}")
            return False

    def delete_user(self, user_id: int):
        """Полное удаление пользователя из базы (сброс)"""
        try:
            # Сначала удаляем связанные данные (фидбек), чтобы не было ошибок
            self.cursor.execute("DELETE FROM signal_feedback WHERE user_id = ?", (user_id,))
            
            # Удаляем самого пользователя
            self.cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при удалении пользователя: {e}")
            return False

    def is_user_banned(self, user_id: int) -> bool:
        """Проверка блокировки пользователя"""
        try:
            self.cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
            result = self.cursor.fetchone()
            return result[0] == 1 if result else False
        except Exception:
            return False

    def close(self):
        """Закрытие соединения с базой данных"""
        self.conn.close()


# Глобальный экземпляр базы данных
db = Database()

