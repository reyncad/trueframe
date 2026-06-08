using System.Security.Cryptography;
using System.Text;

namespace TrueFrameUI.Services
{
    /// <summary>
    /// PBKDF2 tabanlı şifre hash'leme.
    /// Her şifre için benzersiz bir salt üretir; salt ve hash birlikte saklanır.
    ///
    /// Format: Base64(salt[16 bytes] + hash[32 bytes])
    ///
    /// Güvenlik notu: SHA-256 ile saltsız hash'in (önceki implementasyon)
    /// aksine rainbow table ve lookup table saldırılarına karşı dayanıklıdır.
    /// </summary>
    public static class PasswordHasher
    {
        private const int SaltSize       = 16;   // byte
        private const int HashSize       = 32;   // byte (SHA-256)
        private const int Iterations     = 100_000;
        private static readonly HashAlgorithmName Algorithm = HashAlgorithmName.SHA256;

        /// <summary>
        /// Şifreyi hash'ler. Her çağrıda farklı salt üretilir.
        /// </summary>
        public static string Hash(string password)
        {
            var salt = RandomNumberGenerator.GetBytes(SaltSize);
            var hash = Rfc2898DeriveBytes.Pbkdf2(
                Encoding.UTF8.GetBytes(password),
                salt,
                Iterations,
                Algorithm,
                HashSize
            );
            // salt + hash → Base64
            var combined = new byte[SaltSize + HashSize];
            Buffer.BlockCopy(salt, 0, combined, 0, SaltSize);
            Buffer.BlockCopy(hash, 0, combined, SaltSize, HashSize);
            return Convert.ToBase64String(combined);
        }

        /// <summary>
        /// Şifreyi kayıtlı hash ile doğrular.
        /// Eski SHA-256 hash'leri de (geçiş dönemi için) tanır.
        /// </summary>
        public static bool Verify(string password, string storedHash)
        {
            // Yeni PBKDF2 formatı
            if (TryVerifyPbkdf2(password, storedHash))
                return true;

            // Geçiş dönemi: eski SHA-256 format (saltsız hex string)
            if (IsLegacyHash(storedHash))
                return VerifyLegacy(password, storedHash);

            return false;
        }

        private static bool TryVerifyPbkdf2(string password, string storedHash)
        {
            try
            {
                var combined = Convert.FromBase64String(storedHash);
                if (combined.Length != SaltSize + HashSize)
                    return false;

                var salt = combined[..SaltSize];
                var storedBytes = combined[SaltSize..];

                var computedHash = Rfc2898DeriveBytes.Pbkdf2(
                    Encoding.UTF8.GetBytes(password),
                    salt,
                    Iterations,
                    Algorithm,
                    HashSize
                );

                // Sabit zamanlı karşılaştırma (timing attack'a karşı)
                return CryptographicOperations.FixedTimeEquals(computedHash, storedBytes);
            }
            catch
            {
                return false;
            }
        }

        private static bool IsLegacyHash(string hash)
            => hash.Length == 64 && hash.All(c => "0123456789ABCDEFabcdef".Contains(c));

        private static bool VerifyLegacy(string password, string legacyHash)
        {
            var computed = Convert.ToHexString(
                SHA256.HashData(Encoding.UTF8.GetBytes(password))
            );
            return string.Equals(computed, legacyHash, StringComparison.OrdinalIgnoreCase);
        }
    }
}
