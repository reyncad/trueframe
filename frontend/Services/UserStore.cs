using System.Text.Json;

namespace TrueFrameUI.Services
{
    /// <summary>
    /// JSON dosya tabanlı kullanıcı deposu.
    ///
    /// Güvenlik değişiklikleri (önceki versiyona göre):
    ///   - Şifreler artık PBKDF2 + salt ile hash'leniyor (PasswordHasher kullanılıyor)
    ///   - Eski SHA-256 hash'leri geçiş dönemi için destekleniyor
    ///
    /// Sınırlamalar (MVP — production'a geçişte göz önünde bulundurulmalı):
    ///   - Tek process için thread-safe; çoklu instance'da race condition oluşur
    ///   - Büyük kullanıcı tabanı için SQLite veya gerçek DB önerilir
    /// </summary>
    public class UserRecord
    {
        public string FullName     { get; set; } = "";
        public string PasswordHash { get; set; } = "";
    }

    public class UserStore
    {
        private readonly string _filePath;
        private Dictionary<string, UserRecord> _users;
        private readonly object _lock = new();

        public UserStore(IWebHostEnvironment env)
        {
            _filePath = Path.Combine(env.ContentRootPath, "Data", "users.json");
            Directory.CreateDirectory(Path.GetDirectoryName(_filePath)!);
            _users = Load();
        }

        private Dictionary<string, UserRecord> Load()
        {
            if (!File.Exists(_filePath)) return new();
            try
            {
                var json = File.ReadAllText(_filePath);
                return JsonSerializer.Deserialize<Dictionary<string, UserRecord>>(json) ?? new();
            }
            catch { return new(); }
        }

        private void Save()
        {
            var tmp = _filePath + ".tmp";
            File.WriteAllText(tmp, JsonSerializer.Serialize(_users, new JsonSerializerOptions { WriteIndented = true }));
            File.Move(tmp, _filePath, overwrite: true);  // Atomic write
        }

        public bool Exists(string username)
        {
            lock (_lock) return _users.ContainsKey(username.ToLower());
        }

        public bool Register(string username, string fullName, string password)
        {
            lock (_lock)
            {
                var key = username.ToLower();
                if (_users.ContainsKey(key)) return false;
                _users[key] = new UserRecord
                {
                    FullName     = fullName,
                    PasswordHash = PasswordHasher.Hash(password)   // PBKDF2 + salt
                };
                Save();
                return true;
            }
        }

        public UserRecord? Login(string username, string password)
        {
            lock (_lock)
            {
                var key = username.ToLower();
                if (!_users.TryGetValue(key, out var user)) return null;

                // PBKDF2 doğrulama (eski SHA-256 hash'ler de desteklenir)
                if (!PasswordHasher.Verify(password, user.PasswordHash)) return null;

                // Geçiş: Eski SHA-256 hash'ini PBKDF2 ile yenile
                if (user.PasswordHash.Length == 64)
                {
                    user.PasswordHash = PasswordHasher.Hash(password);
                    Save();
                }

                return user;
            }
        }
    }
}
