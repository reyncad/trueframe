using Microsoft.AspNetCore.Mvc;

namespace TrueFrameUI.Controllers;

public class LanguageController : Controller
{
    [HttpGet]
    public IActionResult Switch(string lang, string returnUrl = "/")
    {
        var allowed = new[] { "tr", "en" };
        if (!allowed.Contains(lang)) lang = "tr";

        Response.Cookies.Append("lang", lang, new CookieOptions
        {
            Expires = DateTimeOffset.UtcNow.AddYears(1),
            IsEssential = true,
            SameSite = SameSiteMode.Lax
        });

        if (!Url.IsLocalUrl(returnUrl)) returnUrl = "/";
        return Redirect(returnUrl);
    }
}
