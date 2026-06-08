using Microsoft.AspNetCore.Mvc;
using TrueFrameUI.Services;

namespace TrueFrameUI.Controllers
{
    public class AuthController : Controller
    {
        private readonly UserStore _users;

        public AuthController(UserStore users)
        {
            _users = users;
        }

        public IActionResult Login() => View();

        public IActionResult Register() => View();

        /// <summary>
        /// Misafir girişi — session'a 3 analiz hakkı yükler.
        /// </summary>
        public IActionResult Guest()
        {
            // Session fixation önlemi: yeni session başlat
            HttpContext.Session.Clear();
            HttpContext.Session.SetString("UserType",   "Guest");
            HttpContext.Session.SetString("GuestLimit", "3");
            return RedirectToAction("Upload", "Analysis");
        }

        /// <summary>
        /// POST /Auth/Login
        /// [ValidateAntiForgeryToken] Program.cs'deki global filtre ile uygulanır.
        /// </summary>
        [HttpPost]
        public IActionResult Login(string username, string password)
        {
            if (string.IsNullOrWhiteSpace(username) || string.IsNullOrWhiteSpace(password))
            {
                ViewBag.Error = "Kullanıcı adı ve şifre boş bırakılamaz.";
                return View();
            }

            var user = _users.Login(username, password);
            if (user == null)
            {
                // Hangi alanın yanlış olduğunu belirtme (bilgi sızdırma riski)
                ViewBag.Error = "Kullanıcı adı veya şifre hatalı.";
                return View();
            }

            // Session fixation önlemi: login öncesi session'ı temizle
            HttpContext.Session.Clear();

            HttpContext.Session.SetString("UserType", "Registered");
            HttpContext.Session.SetString("UserEmail", username.ToLower());
            HttpContext.Session.SetString("FullName",  user.FullName);
            return RedirectToAction("Upload", "Analysis");
        }

        /// <summary>
        /// POST /Auth/Register
        /// </summary>
        [HttpPost]
        public IActionResult Register(string fullName, string username, string password)
        {
            if (string.IsNullOrWhiteSpace(username) ||
                string.IsNullOrWhiteSpace(password)  ||
                string.IsNullOrWhiteSpace(fullName))
            {
                ViewBag.Error = "Tüm alanları doldurunuz.";
                return View();
            }

            if (password.Length < 8)
            {
                ViewBag.Error = "Şifre en az 8 karakter olmalıdır.";
                return View();
            }

            if (!_users.Register(username, fullName, password))
            {
                ViewBag.Error = "Bu kullanıcı adı zaten alınmış.";
                return View();
            }

            // Session fixation önlemi
            HttpContext.Session.Clear();

            HttpContext.Session.SetString("UserType", "Registered");
            HttpContext.Session.SetString("UserEmail", username.ToLower());
            HttpContext.Session.SetString("FullName",  fullName);
            return RedirectToAction("Upload", "Analysis");
        }

        public IActionResult Logout()
        {
            HttpContext.Session.Clear();
            return RedirectToAction("Index", "Home");
        }
    }
}
