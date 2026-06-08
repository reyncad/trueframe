using Microsoft.AspNetCore.Mvc;
using System.Text.Json;
using TrueFrameUI.Models;

namespace TrueFrameUI.Controllers
{
    public class AnalysisController : Controller
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private const string ApiUrl = "http://127.0.0.1:8000/api/analyze";

        public AnalysisController(IHttpClientFactory httpClientFactory)
        {
            _httpClientFactory = httpClientFactory;
        }

        public IActionResult Upload()
        {
            if (string.IsNullOrEmpty(HttpContext.Session.GetString("UserType")))
            {
                TempData["AccessError"] = "Analiz yapabilmek için lütfen giriş yapınız veya misafir olarak devam ediniz.";
                return RedirectToAction("Login", "Auth");
            }
            return View();
        }

        [HttpPost]
        public async Task<IActionResult> Result(IFormFile imageFile, bool realFakeSelected, bool qualitySelected)
        {
            if (imageFile == null || imageFile.Length == 0)
            {
                ViewBag.Error = "Lütfen analiz için bir görsel yükleyiniz.";
                return View("Upload");
            }

            var allowedExtensions = new[] { ".jpg", ".jpeg", ".png", ".webp" };
            var extension = Path.GetExtension(imageFile.FileName).ToLower();

            if (!allowedExtensions.Contains(extension))
            {
                ViewBag.Error = "Desteklenmeyen dosya formatı. Lütfen JPG, PNG veya WEBP formatında bir görsel yükleyiniz.";
                return View("Upload");
            }

            if (imageFile.Length > 5 * 1024 * 1024)
            {
                ViewBag.Error = "Dosya boyutu çok büyük. Lütfen en fazla 5 MB boyutunda bir görsel yükleyiniz.";
                return View("Upload");
            }

            var userType = HttpContext.Session.GetString("UserType");

            if (string.IsNullOrEmpty(userType))
            {
                TempData["AccessError"] = "Analiz yapabilmek için lütfen giriş yapınız veya misafir olarak devam ediniz.";
                return RedirectToAction("Login", "Auth");
            }

            if (userType == "Guest")
            {
                int.TryParse(HttpContext.Session.GetString("GuestLimit"), out int guestLimit);
                if (guestLimit <= 0)
                {
                    ViewBag.Error = "Misafir analiz hakkınız doldu. Daha fazla analiz yapmak için lütfen giriş yapınız.";
                    return View("Upload");
                }
                HttpContext.Session.SetString("GuestLimit", (guestLimit - 1).ToString());
            }

            if (!realFakeSelected && !qualitySelected)
            {
                realFakeSelected = true;
                qualitySelected  = true;
            }

            var uploadsFolder = Path.Combine(Directory.GetCurrentDirectory(), "wwwroot", "uploads");
            Directory.CreateDirectory(uploadsFolder);
            var uniqueFileName = Guid.NewGuid().ToString() + extension;
            var filePath = Path.Combine(uploadsFolder, uniqueFileName);

            using (var stream = new FileStream(filePath, FileMode.Create))
                await imageFile.CopyToAsync(stream);

            AnalysisViewModel model;
            try
            {
                var client = _httpClientFactory.CreateClient();
                client.Timeout = TimeSpan.FromSeconds(120);
                using var form = new MultipartFormDataContent();
                await using var fileStream = System.IO.File.OpenRead(filePath);
                var streamContent = new StreamContent(fileStream);
                streamContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(imageFile.ContentType);
                form.Add(streamContent, "image", imageFile.FileName);

                var response = await client.PostAsync(ApiUrl, form);
                var json     = await response.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(json);
                var data = doc.RootElement;

                // ── Kalite alanları ──────────────────────────────────────
                var hasQ   = data.TryGetProperty("quality", out var q) && q.ValueKind == JsonValueKind.Object;
                var hasDim = hasQ && q.TryGetProperty("dimensions",  out var _) ;
                var dims   = hasDim ? q.GetProperty("dimensions") : default;

                double D(JsonElement el, string key) =>
                    el.ValueKind == JsonValueKind.Object && el.TryGetProperty(key, out var v) && v.ValueKind != JsonValueKind.Null
                        ? v.GetDouble() : 0;

                string S(JsonElement el, string key, string def = "") =>
                    el.ValueKind == JsonValueKind.Object && el.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String
                        ? v.GetString() ?? def : def;

                double? DN(JsonElement el, string key) =>
                    el.ValueKind == JsonValueKind.Object && el.TryGetProperty(key, out var v)
                    && v.ValueKind != JsonValueKind.Null && v.ValueKind != JsonValueKind.Undefined
                        ? v.GetDouble() : null;

                var hasTech = hasQ && q.TryGetProperty("technical",  out var _);
                var hasExp  = hasQ && q.TryGetProperty("exposure",   out var _);
                var hasCol  = hasQ && q.TryGetProperty("color",      out var _);
                var hasGeo  = hasQ && q.TryGetProperty("geometry",   out var _);
                var hasExif = hasQ && q.TryGetProperty("exif",       out var _);

                var tech = hasTech ? q.GetProperty("technical") : default;
                var exp  = hasExp  ? q.GetProperty("exposure")  : default;
                var col  = hasCol  ? q.GetProperty("color")     : default;
                var geo  = hasGeo  ? q.GetProperty("geometry")  : default;
                var exif = hasExif ? q.GetProperty("exif")      : default;

                // IQA metrik listesi
                var iqaList = new List<IqaMetricItem>();
                if (hasQ && q.TryGetProperty("iqa_metrics", out var iqaArr) && iqaArr.ValueKind == JsonValueKind.Array)
                {
                    foreach (var item in iqaArr.EnumerateArray())
                    {
                        var entry = new IqaMetricItem
                        {
                            Label     = S(item, "label"),
                            Direction = S(item, "direction"),
                            GoodMin   = D(item, "good_min"),
                            GoodMax   = D(item, "good_max"),
                            Error     = S(item, "error"),
                        };
                        if (item.TryGetProperty("score", out var sc) && sc.ValueKind != JsonValueKind.Null)
                            entry.Score = sc.GetDouble();
                        iqaList.Add(entry);
                    }
                }

                // Profil kontrol listesi
                var checks = new List<CheckItem>();
                if (hasQ && q.TryGetProperty("checks", out var chkArr) && chkArr.ValueKind == JsonValueKind.Array)
                {
                    foreach (var c in chkArr.EnumerateArray())
                    {
                        checks.Add(new CheckItem
                        {
                            Name   = S(c, "name"),
                            Passed = c.TryGetProperty("passed", out var p) && p.GetBoolean(),
                            Value  = S(c, "value"),
                            Needed = S(c, "needed"),
                        });
                    }
                }

                model = new AnalysisViewModel
                {
                    ImagePath        = "/uploads/" + uniqueFileName,
                    RealFakeSelected = realFakeSelected,
                    QualitySelected  = qualitySelected,

                    // AI Tespit
                    Label           = data.TryGetProperty("label",      out var lbl) ? lbl.GetString() : "-",
                    AiProbability   = data.TryGetProperty("fake_prob",  out var fp)  ? fp.GetDouble()  : 0,
                    RealProbability = data.TryGetProperty("real_prob",  out var rp)  ? rp.GetDouble()  : 0,
                    ConfidenceScore = data.TryGetProperty("confidence", out var cf)  ? cf.GetDouble()  : 0,
                    IsManipulated   = data.TryGetProperty("is_manipulated", out var im) && im.ValueKind == JsonValueKind.True,

                    // Kalite — 6D
                    QualityScore  = hasQ ? D(q, "quality_score") : 0,
                    Verdict       = hasQ ? S(q, "verdict") : "",
                    ProfileLabel  = hasQ ? S(q, "profile_label") : "",
                    ProfilePass   = hasQ && q.TryGetProperty("profile_pass",  out var pp) ? pp.GetInt32() : 0,
                    ProfileTotal  = hasQ && q.TryGetProperty("profile_total", out var pt) ? pt.GetInt32() : 0,

                    Sharpness  = D(dims, "keskinlik"),
                    Noise      = D(dims, "gurultu"),
                    Exposure   = D(dims, "pozlama"),
                    Color      = D(dims, "renk"),
                    Aesthetics = D(dims, "estetik"),
                    Technical  = D(dims, "teknik"),

                    // Teknik Bilgi
                    ImgWidth    = hasTech && tech.TryGetProperty("width",  out var w) ? w.GetInt32() : 0,
                    ImgHeight   = hasTech && tech.TryGetProperty("height", out var h) ? h.GetInt32() : 0,
                    Megapixels  = D(tech, "megapixels"),
                    ImgFormat   = S(tech, "format"),
                    ColorMode   = S(tech, "color_mode"),
                    Dpi         = DN(tech, "dpi"),

                    // EXIF
                    ExifDatetime = hasExif ? S(exif, "datetime") : "",

                    // Pozlama
                    ExposureLabel  = S(exp, "label"),
                    HighlightClip  = D(exp, "highlight_clip"),
                    ShadowClip     = D(exp, "shadow_clip"),
                    DynamicRange   = D(exp, "dynamic_range"),
                    AvgBrightness  = D(exp, "avg_brightness"),

                    // Renk & Gürültü
                    ColorCast        = S(col, "cast"),
                    ColorTemperature = DN(col, "temperature"),
                    ColorTint        = DN(col, "tint"),
                    Saturation       = DN(col, "saturation"),
                    ColorNoise       = S(col, "noise"),

                    // Geometri & Blur
                    BlurType        = S(geo, "blur_type"),
                    BlurLabel       = S(geo, "blur_label"),
                    TiltAngle       = DN(geo, "tilt_angle"),
                    TiltLabel       = S(geo, "tilt_label"),
                    TiltConfidence  = DN(geo, "tilt_confidence"),
                    MoireScore      = D(geo, "moire_score"),
                    MoireLabel      = S(geo, "moire_label", "Yok"),

                    IqaMetrics = iqaList,
                    Checks     = checks,

                    StatusMessage = "Analiz başarıyla tamamlandı."
                };
            }
            catch (Exception ex)
            {
                model = new AnalysisViewModel
                {
                    ImagePath        = "/uploads/" + uniqueFileName,
                    RealFakeSelected = realFakeSelected,
                    QualitySelected  = qualitySelected,
                    ErrorMessage     = $"Analiz servisine bağlanılamadı: {ex.Message}",
                    StatusMessage    = "Hata"
                };
            }

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
