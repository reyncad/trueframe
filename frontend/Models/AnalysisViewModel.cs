namespace TrueFrameUI.Models
{
    public class IqaMetricItem
    {
        public string? Label { get; set; }
        public double? Score { get; set; }
        public string? Direction { get; set; }
        public double GoodMin { get; set; }
        public double GoodMax { get; set; }
        public string? Error { get; set; }
    }

    public class CheckItem
    {
        public string? Name   { get; set; }
        public bool?   Passed { get; set; }   // FIX: null = bilinmiyor (N/A), gösterim: — yerine ✗ değil
        public string? Value  { get; set; }
        public string? Needed { get; set; }
    }

    public class AnalysisViewModel
    {
        public string? ImagePath { get; set; }
        public bool RealFakeSelected { get; set; }
        public bool QualitySelected { get; set; }

        // AI Tespit
        public string? Label { get; set; }
        public double AiProbability { get; set; }
        public double RealProbability { get; set; }
        public double ConfidenceScore { get; set; }
        public bool IsManipulated { get; set; }
        public double ManipScore { get; set; }

        // Kalite — 6D
        public double QualityScore { get; set; }
        public string? Verdict { get; set; }
        public string? ProfileLabel { get; set; }
        public int ProfilePass { get; set; }
        public int ProfileTotal { get; set; }

        public double Sharpness { get; set; }
        public double Noise { get; set; }
        public double Exposure { get; set; }
        public double Color { get; set; }
        public double Aesthetics { get; set; }
        public double Technical { get; set; }

        // Teknik Bilgi
        public int ImgWidth { get; set; }
        public int ImgHeight { get; set; }
        public double Megapixels { get; set; }
        public string? ImgFormat { get; set; }
        public string? ColorMode { get; set; }
        public double? Dpi { get; set; }

        // EXIF
        public string? ExifDatetime { get; set; }

        // Pozlama
        public string? ExposureLabel { get; set; }
        public double HighlightClip { get; set; }
        public double ShadowClip { get; set; }
        public double DynamicRange { get; set; }
        public double AvgBrightness { get; set; }

        // Renk & Gürültü
        public string? ColorCast { get; set; }
        public double? ColorTemperature { get; set; }
        public double? ColorTint { get; set; }
        public double? Saturation { get; set; }
        public string? ColorNoise { get; set; }

        // Geometri & Blur
        public string? BlurType { get; set; }
        public string? BlurLabel { get; set; }
        public double? TiltAngle { get; set; }
        public string? TiltLabel { get; set; }
        public double? TiltConfidence { get; set; }
        public double MoireScore { get; set; }
        public string? MoireLabel { get; set; }

        // IQA Metrikleri
        public List<IqaMetricItem> IqaMetrics { get; set; } = new();

        // Profil kontrol listesi
        public List<CheckItem> Checks { get; set; } = new();

        public string? StatusMessage  { get; set; }
        public string? ErrorMessage   { get; set; }

        // Geçmiş / Details sayfası için ek alanlar
        public string? CreatedAt    { get; set; }
        public string? OriginalName { get; set; }
    }
}
