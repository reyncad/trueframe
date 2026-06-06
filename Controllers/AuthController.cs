using Microsoft.AspNetCore.Mvc;

namespace TrueFrameUI.Controllers
{
    public class AuthController : Controller
    {
        public IActionResult Login()
        {
            return View();
        }

        public IActionResult Register()
        {
            return View();
        }

        public IActionResult Guest()
        {
            HttpContext.Session.SetString("UserType", "Guest");
            HttpContext.Session.SetString("GuestLimit", "3");

            return RedirectToAction("Upload", "Analysis");
        }

        [HttpPost]
        public IActionResult Login(string email, string password)
        {
            HttpContext.Session.SetString("UserType", "Registered");
            HttpContext.Session.SetString("UserEmail", email);

            return RedirectToAction("Upload", "Analysis");
        }

        [HttpPost]
        public IActionResult Register(string fullName, string email, string password)
        {
            HttpContext.Session.SetString("UserType", "Registered");
            HttpContext.Session.SetString("UserEmail", email);
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