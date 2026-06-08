using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace TrueFrameUI.Services
{
    public class UserRecord
    {
        public string FullName { get; set; } = "";
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
            File.WriteAllText(_filePath, JsonSerializer.Serialize(_users, new JsonSerializerOptions { WriteIndented = true }));
        }

        private static string Hash(string password) =>
            Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(password)));

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
                _users[key] = new UserRecord { FullName = fullName, PasswordHash = Hash(password) };
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
                return user.PasswordHash == Hash(password) ? user : null;
            }
        }
    }
}
