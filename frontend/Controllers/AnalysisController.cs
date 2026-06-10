using Microsoft.AspNetCore.Mvc;
using System.Text.Json;
using TrueFrameUI.Models;

namespace TrueFrameUI.Controllers
{
    public class AnalysisController : Controller
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly IConfiguration     _config;

        // URL'ler appsettings.json veya ortam değişkeninden okunur
        private string ApiUrl        => _config["ApiUrl"]        ?? "http://localhost:8000/api/analyze";
        private string HistoryApiUrl => _config["HistoryApiUrl"] ?? "http://localhost:8000/api/history";
        private string ApiKey        => _config["TRUEFRAME_API_KEY"] ?? "";

        private static readonly JsonSerializerOptions _jsonOpts = new()
        {
            PropertyNameCaseInsensitive = true
        };

        public AnalysisController(IHttpClientFactory httpClientFactory, IConfiguration config)
        {
            _httpClientFactory = httpClientFactory;
            _config            = config;
        }

        // ── Upload ────────────────────────────────────────────

        public IActionResult Upload()
        {
            if (string.IsNullOrEmpty(HttpContext.Session.GetString("UserType")))
            {
                TempData["AccessError"] = "Analiz yapabilmek için lütfen giriş yapınız veya misafir olarak devam ediniz.";
                return RedirectToAction("Login", "Auth");
            }
            return View();
        }

        // ── Result ────────────────────────────────────────────

        [HttpPost]
        [IgnoreAntiforgeryToken]   // Dosya yükleme form'unda AntiForgery Token var — Program.cs global filtreden muaf
        public async Task<IActionResult> Result(IFormFile imageFile, bool realFakeSelected, bool qualitySelected, string? profile)
        {
            if (imageFile == null || imageFile.Length == 0)
            {
                ViewBag.Error = "Lütfen analiz için bir görsel yükleyiniz.";
                return View("Upload");
            }

            var allowedExtensions = new[] { ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp" };
            var extension         = Path.GetExtension(imageFile.FileName).ToLower();

            if (!allowedExtensions.Contains(extension))
            {
                ViewBag.Error = "Desteklenmeyen dosya formatı. Lütfen JPG, PNG, WEBP, TIFF veya BMP formatında bir görsel yükleyiniz.";
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

            // Görseli belleğe al — diske yazma, disk dolumunu önle
            byte[] imageBytes;
            using (var ms = new System.IO.MemoryStream())
            {
                await imageFile.CopyToAsync(ms);
                imageBytes = ms.ToArray();
            }

            // Preview için base64 data URI — fiziksel dosya yok
            var mimeType  = imageFile.ContentType;
            var previewUri = $"data:{mimeType};base64,{Convert.ToBase64String(imageBytes)}";

            // Backend'e göndermek için geçici dosya (IQA modeli disk okur)
            var tmpPath = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString() + extension);
            AnalysisViewModel model;
            try
            {
                await System.IO.File.WriteAllBytesAsync(tmpPath, imageBytes);

                var client = _httpClientFactory.CreateClient();
                client.Timeout = TimeSpan.FromSeconds(180);   // IQA model yükleme toleransı

                using var form = new MultipartFormDataContent();
                await using var fileStream   = System.IO.File.OpenRead(tmpPath);
                var streamContent = new StreamContent(fileStream);
                streamContent.Headers.ContentType =
                    new System.Net.Http.Headers.MediaTypeHeaderValue(imageFile.ContentType);
                form.Add(streamContent, "image", imageFile.FileName);
                form.Add(new StringContent(profile ?? "none"), "profile");
                // FIX: Analiz türü artık backend'e taşınıyor — yalnızca "kalite" seçiliyse
                // AI/sahte tespit modeli backend'de hiç çağrılmaz.
                form.Add(new StringContent(realFakeSelected ? "true" : "false"), "analyze_ai");
                form.Add(new StringContent(qualitySelected  ? "true" : "false"), "analyze_quality");
                // Kullanıcı izolasyonu: kayıt sahibi (kayıtlı e-posta veya 'guest')
                form.Add(new StringContent(CurrentUserKey()), "user");

                // İç ağ API key header'ı
                if (!string.IsNullOrEmpty(ApiKey))
                    client.DefaultRequestHeaders.Add("X-TrueFrame-Key", ApiKey);

                var response = await client.PostAsync(ApiUrl, form);
                var json     = await response.Content.ReadAsStringAsync();

                var apiResponse = JsonSerializer.Deserialize<AnalysisApiResponse>(json, _jsonOpts);
                if (apiResponse == null)
                    throw new InvalidOperationException("API yanıtı boş geldi.");

                // Kalite hatası varsa kullanıcıya göster ama akışı durdurmayalım
                var qualityError = apiResponse.Quality?.Error;

                model = MapToViewModel(apiResponse, previewUri,
                                       realFakeSelected, qualitySelected, qualityError,
                                       apiResponse.SavedId);
            }
            catch (TaskCanceledException)
            {
                model = ErrorViewModel(previewUri, realFakeSelected, qualitySelected,
                    "Analiz zaman aşımına uğradı. Lütfen daha küçük bir görsel deneyin veya daha sonra tekrar deneyiniz.");
            }
            catch (HttpRequestException)
            {
                model = ErrorViewModel(previewUri, realFakeSelected, qualitySelected,
                    "Analiz servisine bağlanılamadı. Lütfen birkaç saniye bekleyip tekrar deneyiniz.");
            }
            catch (JsonException)
            {
                model = ErrorViewModel(previewUri, realFakeSelected, qualitySelected,
                    "Analiz servisi beklenmeyen bir yanıt döndürdü.");
            }
            catch (Exception ex)
            {
                model = ErrorViewModel(previewUri, realFakeSelected, qualitySelected,
                    $"Beklenmeyen hata: {ex.Message}");
            }
            finally
            {
                // Geçici dosyayı temizle
                if (System.IO.File.Exists(tmpPath))
                    System.IO.File.Delete(tmpPath);
            }

            return View(model);
        }

        // ── History ───────────────────────────────────────────

        public async Task<IActionResult> History(
            string? result, double? minScore, double? maxScore,
            string? dateFrom, string? dateTo, string? fileType, string? q, string? profile)
        {
            var userType = HttpContext.Session.GetString("UserType");
            if (userType != "Registered")
            {
                TempData["AccessError"] = "Kayıtlarım sayfası yalnızca kayıtlı kullanıcılar için kullanılabilir.";
                return RedirectToAction("Login", "Auth");
            }

            var viewModel = new HistoryViewModel
            {
                FilterResult   = result,
                FilterMinScore = minScore,
                FilterMaxScore = maxScore,
                FilterDateFrom = dateFrom,
                FilterDateTo   = dateTo,
                FilterFileType = fileType,
                FilterQuery    = q,
                FilterProfile  = profile,
            };
            try
            {
                var client = _httpClientFactory.CreateClient();
                client.Timeout = TimeSpan.FromSeconds(15);

                if (!string.IsNullOrEmpty(ApiKey))
                    client.DefaultRequestHeaders.Add("X-TrueFrame-Key", ApiKey);

                // Filtre parametrelerini backend sorgusuna taşı
                var qs = new List<string>();
                void AddParam(string key, string? val)
                {
                    if (!string.IsNullOrWhiteSpace(val))
                        qs.Add($"{key}={Uri.EscapeDataString(val.Trim())}");
                }
                AddParam("result",    result);
                AddParam("min_score", minScore?.ToString(System.Globalization.CultureInfo.InvariantCulture));
                AddParam("max_score", maxScore?.ToString(System.Globalization.CultureInfo.InvariantCulture));
                AddParam("date_from", dateFrom);
                AddParam("date_to",   dateTo);
                AddParam("file_type", fileType);
                AddParam("profile",   profile);
                AddParam("q",         q);
                AddParam("user",      CurrentUserKey());   // kullanıcı izolasyonu
                var url = HistoryApiUrl + (qs.Count > 0 ? "?" + string.Join("&", qs) : "");

                var response = await client.GetAsync(url);
                var json     = await response.Content.ReadAsStringAsync();

                using var doc  = JsonDocument.Parse(json);
                var root = doc.RootElement;

                if (root.TryGetProperty("warning", out var warn))
                    viewModel.Warning = warn.GetString();

                if (root.TryGetProperty("items", out var items) && items.ValueKind == JsonValueKind.Array)
                {
                    foreach (var item in items.EnumerateArray())
                    {
                        viewModel.Items.Add(new HistoryItemViewModel
                        {
                            Id        = item.TryGetProperty("id",       out var id)  ? id.GetInt32()    : 0,
                            Name      = item.TryGetProperty("name",     out var nm)  ? nm.GetString()   ?? "" : "",
                            Profile   = item.TryGetProperty("profile",  out var pr)  ? pr.GetString()   ?? "" : "",
                            Overall   = item.TryGetProperty("overall",  out var ov)  && ov.ValueKind != JsonValueKind.Null ? ov.GetDouble() : null,
                            Verdict   = item.TryGetProperty("verdict",  out var vr)  ? vr.GetString()   ?? "" : "",
                            Thumbnail = item.TryGetProperty("thumbnail",out var th)  ? th.GetString()   ?? "" : "",
                            Label     = item.TryGetProperty("label",    out var lb)  ? lb.GetString()   ?? "" : "",
                            FakeProb  = item.TryGetProperty("fake_prob",out var fp)  && fp.ValueKind != JsonValueKind.Null ? fp.GetDouble() : null,
                            RealProb  = item.TryGetProperty("real_prob",out var rp)  && rp.ValueKind != JsonValueKind.Null ? rp.GetDouble() : null,
                            CreatedAt = item.TryGetProperty("created_at",out var ca) ? ca.GetString()   ?? "" : "",
                        });
                    }
                }
            }
            catch (Exception ex)
            {
                viewModel.Error = $"Geçmiş kayıtlar yüklenemedi: {ex.Message}";
            }

            return View(viewModel);
        }

        // ── Details ───────────────────────────────────────────

        public async Task<IActionResult> Details(int id)
        {
            var userType = HttpContext.Session.GetString("UserType");
            if (userType != "Registered")
            {
                TempData["AccessError"] = "Rapor detaylarını görüntülemek için lütfen giriş yapınız.";
                return RedirectToAction("Login", "Auth");
            }

            AnalysisViewModel model;
            try
            {
                var client = _httpClientFactory.CreateClient();
                client.Timeout = TimeSpan.FromSeconds(15);

                if (!string.IsNullOrEmpty(ApiKey))
                    client.DefaultRequestHeaders.Add("X-TrueFrame-Key", ApiKey);

                var response = await client.GetAsync(
                    $"{HistoryApiUrl}/{id}?user={Uri.EscapeDataString(CurrentUserKey())}");

                if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
                {
                    TempData["AccessError"] = "Kayıt bulunamadı.";
                    return RedirectToAction("History");
                }

                var json        = await response.Content.ReadAsStringAsync();
                var apiResponse = JsonSerializer.Deserialize<AnalysisApiResponse>(json, _jsonOpts);

                if (apiResponse == null)
                    throw new InvalidOperationException("Kayıt verisi boş.");

                // Thumbnail detay sayfası için
                using var doc = JsonDocument.Parse(json);
                string thumbnail = doc.RootElement.TryGetProperty("thumbnail", out var th) ? th.GetString() ?? "" : "";
                string createdAt = doc.RootElement.TryGetProperty("created_at", out var ca) ? ca.GetString() ?? "" : "";
                string name      = doc.RootElement.TryGetProperty("name", out var nm) ? nm.GetString() ?? "" : "";

                // Kayıtta hangi analizler çalıştıysa onları göster (eski kayıtlarda flag yok → ikisi de)
                model = MapToViewModel(apiResponse, thumbnail,
                                       apiResponse.Analysis?.Ai ?? true,
                                       apiResponse.Analysis?.Quality ?? true, null);
                model.CreatedAt   = createdAt;
                model.OriginalName = name;
            }
            catch (Exception ex)
            {
                model = new AnalysisViewModel { ErrorMessage = ex.Message };
            }

            return View(model);
        }

        // ── Delete ────────────────────────────────────────────
        // FIX: backend delete_analysis() hiç bağlanmamıştı — kayıt silme eklendi.
        [HttpPost]
        public async Task<IActionResult> Delete(int id)
        {
            var userType = HttpContext.Session.GetString("UserType");
            if (userType != "Registered")
            {
                TempData["AccessError"] = "Bu işlem için giriş yapmalısınız.";
                return RedirectToAction("Login", "Auth");
            }

            try
            {
                var client = _httpClientFactory.CreateClient();
                client.Timeout = TimeSpan.FromSeconds(15);
                if (!string.IsNullOrEmpty(ApiKey))
                    client.DefaultRequestHeaders.Add("X-TrueFrame-Key", ApiKey);

                var response = await client.PostAsync(
                    $"{HistoryApiUrl}/{id}/delete?user={Uri.EscapeDataString(CurrentUserKey())}", null);
                if (!response.IsSuccessStatusCode)
                    TempData["AccessError"] = "Kayıt silinemedi.";
            }
            catch
            {
                TempData["AccessError"] = "Silme servisi yanıt vermedi.";
            }
            return RedirectToAction("History");
        }

        // ── HTML Rapor (proxy) ────────────────────────────────
        // FIX: backend /api/report/<id> raporu UI'dan erişilemiyordu.
        // Backend iç ağda olduğundan frontend proxy'ler ve API key'i ekler.
        public async Task<IActionResult> Report(int id)
        {
            var userType = HttpContext.Session.GetString("UserType");
            if (userType != "Registered")
            {
                TempData["AccessError"] = "Raporu görüntülemek için lütfen giriş yapınız.";
                return RedirectToAction("Login", "Auth");
            }

            try
            {
                var client = _httpClientFactory.CreateClient();
                client.Timeout = TimeSpan.FromSeconds(20);
                if (!string.IsNullOrEmpty(ApiKey))
                    client.DefaultRequestHeaders.Add("X-TrueFrame-Key", ApiKey);

                // .../api/history → .../api/report
                var reportUrl = HistoryApiUrl.Replace("/api/history", "/api/report");
                var response = await client.GetAsync(
                    $"{reportUrl}/{id}?user={Uri.EscapeDataString(CurrentUserKey())}");

                if (!response.IsSuccessStatusCode)
                {
                    TempData["AccessError"] = "Rapor bulunamadı.";
                    return RedirectToAction("History");
                }

                var htmlContent = await response.Content.ReadAsStringAsync();
                return Content(htmlContent, "text/html; charset=utf-8");
            }
            catch
            {
                TempData["AccessError"] = "Rapor servisi yanıt vermedi.";
                return RedirectToAction("History");
            }
        }

        // ── Yardımcı metodlar ─────────────────────────────────

        /// <summary>
        /// Geçmiş kayıtlarının sahibi: kayıtlı kullanıcı e-postası veya "guest".
        /// Backend bu değerle kayıtları izole eder (kullanıcı başka kullanıcının
        /// kaydını göremez/silemez; misafir analizleri kimsenin listesine düşmez).
        /// </summary>
        private string CurrentUserKey()
        {
            var userType = HttpContext.Session.GetString("UserType");
            if (userType == "Registered")
                return HttpContext.Session.GetString("UserEmail") ?? "guest";
            return "guest";
        }

        private static AnalysisViewModel MapToViewModel(
            AnalysisApiResponse api,
            string imagePath,
            bool realFakeSelected,
            bool qualitySelected,
            string? qualityError,
            int savedId = 0)
        {
            var q    = api.Quality;
            var dims = q?.Dimensions;
            var tech = q?.Technical;
            var exp  = q?.Exposure;
            var col  = q?.Color;
            var geo  = q?.Geometry;
            var exif = q?.Exif;
            var cn   = q?.ColorNoise;
            var sm   = q?.SharpnessMap;
            var hm   = q?.HighlightMap;

            return new AnalysisViewModel
            {
                ImagePath        = imagePath,
                RealFakeSelected = realFakeSelected,
                QualitySelected  = qualitySelected,

                // AI Tespit
                Label           = api.Label          ?? "-",
                AiProbability   = api.FakeProb,
                RealProbability = api.RealProb,
                ConfidenceScore = api.Confidence,
                IsManipulated   = api.IsManipulated,
                ManipScore      = api.ManipScore ?? 0,

                // Kalite — 6D
                QualityScore  = q?.QualityScore  ?? 0,
                Verdict       = q?.Verdict        ?? "",
                ProfileLabel  = q?.ProfileLabel   ?? "",
                ProfilePass   = q?.ProfilePass    ?? 0,
                ProfileTotal  = q?.ProfileTotal   ?? 0,

                Sharpness  = dims?.Keskinlik ?? 0,
                Noise      = dims?.Gurultu   ?? 0,
                Exposure   = dims?.Pozlama   ?? 0,
                Color      = dims?.Renk      ?? 0,
                Aesthetics = dims?.Estetik   ?? 0,
                Technical  = dims?.Teknik    ?? 0,

                // Teknik Bilgi
                ImgWidth    = tech?.Width      ?? 0,
                ImgHeight   = tech?.Height     ?? 0,
                Megapixels  = tech?.Megapixels ?? 0,
                ImgFormat   = tech?.Format,
                ColorMode   = tech?.ColorMode,
                Dpi         = tech?.Dpi,

                // EXIF — tüm alanlar (FIX: yalnızca datetime aktarılıyordu)
                ExifDatetime    = exif?.Datetime ?? "",
                ExifCamera      = exif?.Camera,
                ExifLens        = exif?.Lens,
                ExifIso         = exif?.Iso,
                ExifAperture    = exif?.Aperture,
                ExifShutter     = exif?.Shutter,
                ExifFocalLength = exif?.FocalLength,
                ExifFlash       = exif?.Flash,
                ExifHasGps      = exif?.HasGps,

                // Pozlama (avg_brightness [0-1] → [0-100] dönüşümü)
                ExposureLabel  = exp?.Label          ?? "",
                HighlightClip  = exp?.HighlightClip  ?? 0,
                ShadowClip     = exp?.ShadowClip     ?? 0,
                DynamicRange   = exp?.DynamicRange   ?? 0,
                AvgBrightness  = exp?.AvgBrightness ?? 0,  // API artık [0-255] döndürüyor
                ContrastRms    = exp?.ContrastRms,

                // Renk & Gürültü
                ColorCast             = col?.Cast,
                CastStrength          = col?.CastStrength,
                ColorTemperature      = col?.Temperature,
                ColorTemperatureLabel = col?.TemperatureLabel,
                ColorTint             = col?.Tint,
                Saturation            = col?.Saturation,
                ColorNoise            = col?.Noise,

                // Kroma gürültü detayı (FIX: color_noise hiç aktarılmıyordu)
                LumaNoise             = cn?.LumaNoise,
                ChromaNoise           = cn?.ChromaNoise,
                ColorNoiseSeverity    = cn?.Severity,
                ColorNoiseDescription = cn?.Description,

                // Geometri & Blur
                BlurType       = geo?.BlurType,
                BlurLabel      = geo?.BlurLabel,
                TiltAngle      = geo?.TiltAngle,
                TiltLabel      = geo?.TiltLabel      ?? "",
                TiltConfidence = geo?.TiltConfidence,
                MoireScore     = geo?.MoireScore     ?? 0,
                MoireLabel     = geo?.MoireLabel      ?? "Yok",

                // IQA Metrikleri
                IqaMetrics = q?.IqaMetrics?.Select(m => new IqaMetricItem
                {
                    Label     = m.Label,
                    Score     = m.Score,
                    Direction = m.Direction,
                    GoodMin   = m.GoodMin,
                    GoodMax   = m.GoodMax,
                    Error     = m.Error,
                }).ToList() ?? new(),

                // Profil Kontrol Listesi
                Checks = q?.Checks?.Select(c => new CheckItem
                {
                    Name   = c.Name,
                    Passed = c.Passed,         // FIX: null korunuyor — "N/A" durumu artık ✗ göstermez
                    Value  = c.Value,
                    Needed = c.Needed,
                }).ToList() ?? new(),

                // Bölgesel haritalar
                SharpnessGrid   = sm?.Grid,
                SharpnessRows   = sm?.Rows ?? 0,
                SharpnessCols   = sm?.Cols ?? 0,
                SharpnessGlobal = sm?.GlobalScore ?? 0,
                SharpestRow     = sm?.SharpestCell?.Count >= 2 ? sm.SharpestCell[0] : -1,
                SharpestCol     = sm?.SharpestCell?.Count >= 2 ? sm.SharpestCell[1] : -1,
                SoftestRow      = sm?.SoftestCell?.Count  >= 2 ? sm.SoftestCell[0]  : -1,
                SoftestCol      = sm?.SoftestCell?.Count  >= 2 ? sm.SoftestCell[1]  : -1,

                HighlightGrid        = hm?.Grid,
                HighlightRows        = hm?.Rows ?? 0,
                HighlightCols        = hm?.Cols ?? 0,
                HighlightHasCritical = hm?.HasCritical ?? false,
                HighlightWorstPct    = hm?.WorstPct    ?? 0,
                HighlightGlobalPct   = hm?.GlobalPct   ?? 0,
                HighlightWorstRow    = hm?.WorstCell?.Count >= 2 ? hm.WorstCell[0] : -1,
                HighlightWorstCol    = hm?.WorstCell?.Count >= 2 ? hm.WorstCell[1] : -1,

                SavedId = savedId,

                StatusMessage = string.IsNullOrEmpty(qualityError)
                    ? "Analiz başarıyla tamamlandı."
                    : $"AI tespiti tamamlandı ancak kalite analizi hata verdi: {qualityError}",
            };
        }

        private static AnalysisViewModel ErrorViewModel(
            string imagePath, bool realFake, bool quality, string message) =>
            new()
            {
                ImagePath        = imagePath,
                RealFakeSelected = realFake,
                QualitySelected  = quality,
                ErrorMessage     = message,
                StatusMessage    = "Hata",
            };
    }
}
