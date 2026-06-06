using Microsoft.AspNetCore.Mvc;
using TrueFrameUI.Models;

namespace TrueFrameUI.Controllers
{
    public class AnalysisController : Controller
    {
        public IActionResult Upload()
        {
            return View();
        }

        [HttpPost]
        public IActionResult Result(IFormFile imageFile, bool realFakeSelected, bool qualitySelected)
        {
            if (imageFile == null || imageFile.Length == 0)
            {
                ViewBag.Error = "Lütfen analiz için bir görsel yükleyiniz.";
                return View("Upload");
            }

            var maxFileSize = 5 * 1024 * 1024;

            if (imageFile.Length > maxFileSize)
            {
                ViewBag.Error = "Dosya boyutu çok büyük. Lütfen en fazla 5 MB boyutunda bir görsel yükleyiniz.";
                return View("Upload");
            }

            var allowedExtensions = new[] { ".jpg", ".jpeg", ".png", ".webp" };
            var extension = Path.GetExtension(imageFile.FileName).ToLower();

            if (!allowedExtensions.Contains(extension))
            {
                ViewBag.Error = "Desteklenmeyen dosya formatı. Lütfen JPG, PNG veya WEBP formatında bir görsel yükleyiniz.";
                return View("Upload");
            }

            var userType = HttpContext.Session.GetString("UserType");

            if (userType == "Guest")
            {
                var guestLimitText = HttpContext.Session.GetString("GuestLimit");

                int guestLimit = 0;

                int.TryParse(guestLimitText, out guestLimit);

                if (guestLimit <= 0)
                {
                    ViewBag.Error = "Misafir analiz hakkınız doldu. Daha fazla analiz yapmak için lütfen giriş yapınız veya kayıt olunuz.";
                    return View("Upload");
                }

                guestLimit--;

                HttpContext.Session.SetString("GuestLimit", guestLimit.ToString());
            }

            if (!realFakeSelected && !qualitySelected)
            {
                realFakeSelected = true;
                qualitySelected = true;
            }

            var simulateServiceError = false;

            if (simulateServiceError)
            {
                ViewBag.Error = "Harici analiz servisine ulaşılamadı. Lütfen daha sonra tekrar deneyiniz.";
                return View("Upload");
            }

            var uploadsFolder = Path.Combine(Directory.GetCurrentDirectory(), "wwwroot", "uploads");

            if (!Directory.Exists(uploadsFolder))
            {
                Directory.CreateDirectory(uploadsFolder);
            }

            var uniqueFileName = Guid.NewGuid().ToString() + extension;
            var filePath = Path.Combine(uploadsFolder, uniqueFileName);

            using (var stream = new FileStream(filePath, FileMode.Create))
            {
                imageFile.CopyTo(stream);
            }

            var model = new AnalysisViewModel
            {
                ImagePath = "/uploads/" + uniqueFileName,

                RealFakeSelected = realFakeSelected,
                QualitySelected = qualitySelected,

                AiProbability = 72,
                RealProbability = 28,
                ConfidenceScore = 91,

                QualityScore = 84,
                Sharpness = 82,
                Contrast = 78,
                NoiseLevel = 18,
                Usability = 88,

                Explanation = "Görselde ışık dağılımı, doku geçişleri ve bazı detaylarda yapay üretime benzer izler tespit edilmiştir. Bu nedenle sistem görselin yapay zekâ tarafından üretilmiş olma ihtimalini yüksek değerlendirmiştir.",
                StatusMessage = "Analiz başarıyla tamamlandı."
            };

            return View(model);
        }

        public IActionResult History()
        {
            var userType = HttpContext.Session.GetString("UserType");

            if (userType != "Registered")
            {
                TempData["AccessError"] = "Kayıtlarım sayfası yalnızca kayıtlı kullanıcılar için kullanılabilir. Lütfen giriş yapınız.";
                return RedirectToAction("Login", "Auth");
            }

            return View();
        }

        public IActionResult Details()
        {
            var userType = HttpContext.Session.GetString("UserType");

            if (userType != "Registered")
            {
                TempData["AccessError"] = "Rapor detaylarını görüntülemek için lütfen giriş yapınız.";
                return RedirectToAction("Login", "Auth");
            }

            return View();
        }
    }
}