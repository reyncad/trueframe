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

        public IActionResult Guest()
        {
            HttpContext.Session.SetString("UserType", "Guest");
            HttpContext.Session.SetString("GuestLimit", "3");
            return RedirectToAction("Upload", "Analysis");
        }

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
                ViewBag.Error = "Kullanıcı adı veya şifre hatalı.";
                return View();
            }

            HttpContext.Session.SetString("UserType", "Registered");
            HttpContext.Session.SetString("UserEmail", username);
            HttpContext.Session.SetString("FullName", user.FullName);
            return RedirectToAction("Upload", "Analysis");
        }

        [HttpPost]
        public IActionResult Register(string fullName, string username, string password)
        {
            if (string.IsNullOrWhiteSpace(username) || string.IsNullOrWhiteSpace(password) || string.IsNullOrWhiteSpace(fullName))
            {
                ViewBag.Error = "Tüm alanları doldurunuz.";
                return View();
            }

            if (password.Length < 6)
            {
                ViewBag.Error = "Şifre en az 6 karakter olmalıdır.";
                return View();
            }

            if (!_users.Register(username, fullName, password))
            {
                ViewBag.Error = "Bu kullanıcı adı zaten alınmış.";
                return View();
            }

            HttpContext.Session.SetString("UserType", "Registered");
            HttpContext.Session.SetString("UserEmail", username);
            HttpContext.Session.SetString("FullName", fullName);
            return RedirectToAction("Upload", "Analysis");
        }

        public IActionResult Logout()
        {
            HttpContext.Session.Clear();
            return RedirectToAction("Index", "Home");
        }
    }
}
