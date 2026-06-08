using System.Text.Json.Serialization;

namespace TrueFrameUI.Models
{
    /// <summary>
    /// Django API'nin /api/analyze endpoint'inden dönen JSON'u karşılayan DTO.
    /// JsonSerializer.Deserialize ile doğrudan eşleme yapılır;
    /// AnalysisController'daki 150+ satır manuel JSON parse bloğunun yerine geçer.
    /// </summary>
    public class AnalysisApiResponse
    {
        // ── Tespit ────────────────────────────────────────────
        [JsonPropertyName("label")]          public string?  Label          { get; set; }
        [JsonPropertyName("confidence")]     public double   Confidence     { get; set; }
        [JsonPropertyName("fake_prob")]      public double   FakeProb       { get; set; }
        [JsonPropertyName("real_prob")]      public double   RealProb       { get; set; }
        [JsonPropertyName("is_ai_generated")]public bool     IsAiGenerated  { get; set; }
        [JsonPropertyName("is_manipulated")] public bool     IsManipulated  { get; set; }
        [JsonPropertyName("manip_score")]    public double?  ManipScore     { get; set; }

        // ── Kalite ────────────────────────────────────────────
        [JsonPropertyName("quality")]        public QualityResponse? Quality { get; set; }
    }

    public class QualityResponse
    {
        [JsonPropertyName("quality_score")]  public double  QualityScore  { get; set; }
        [JsonPropertyName("verdict")]        public string? Verdict       { get; set; }
        [JsonPropertyName("profile_label")]  public string? ProfileLabel  { get; set; }
        [JsonPropertyName("profile_pass")]   public int     ProfilePass   { get; set; }
        [JsonPropertyName("profile_total")]  public int     ProfileTotal  { get; set; }
        [JsonPropertyName("error")]          public string? Error         { get; set; }

        [JsonPropertyName("dimensions")]     public DimensionsResponse?  Dimensions  { get; set; }
        [JsonPropertyName("technical")]      public TechnicalResponse?   Technical   { get; set; }
        [JsonPropertyName("exif")]           public ExifResponse?        Exif        { get; set; }
        [JsonPropertyName("exposure")]       public ExposureResponse?    Exposure    { get; set; }
        [JsonPropertyName("color")]          public ColorResponse?       Color       { get; set; }
        [JsonPropertyName("geometry")]       public GeometryResponse?    Geometry    { get; set; }

        [JsonPropertyName("iqa_metrics")]    public List<IqaMetricItemDto>? IqaMetrics  { get; set; }
        [JsonPropertyName("checks")]         public List<CheckItemDto>?  Checks      { get; set; }
    }

    public class DimensionsResponse
    {
        [JsonPropertyName("keskinlik")]  public double Keskinlik { get; set; }
        [JsonPropertyName("gurultu")]    public double Gurultu   { get; set; }
        [JsonPropertyName("pozlama")]    public double Pozlama   { get; set; }
        [JsonPropertyName("renk")]       public double Renk      { get; set; }
        [JsonPropertyName("estetik")]    public double Estetik   { get; set; }
        [JsonPropertyName("teknik")]     public double Teknik    { get; set; }
    }

    public class TechnicalResponse
    {
        [JsonPropertyName("width")]      public int?    Width     { get; set; }
        [JsonPropertyName("height")]     public int?    Height    { get; set; }
        [JsonPropertyName("megapixels")] public double  Megapixels{ get; set; }
        [JsonPropertyName("format")]     public string? Format    { get; set; }
        [JsonPropertyName("color_mode")] public string? ColorMode { get; set; }
        [JsonPropertyName("dpi")]        public double? Dpi       { get; set; }
    }

    public class ExifResponse
    {
        [JsonPropertyName("datetime")]   public string? Datetime { get; set; }
    }

    public class ExposureResponse
    {
        [JsonPropertyName("label")]          public string? Label         { get; set; }
        [JsonPropertyName("highlight_clip")] public double  HighlightClip { get; set; }
        [JsonPropertyName("shadow_clip")]    public double  ShadowClip    { get; set; }
        [JsonPropertyName("dynamic_range")]  public double  DynamicRange  { get; set; }
        [JsonPropertyName("avg_brightness")] public double  AvgBrightness { get; set; }
    }

    public class ColorResponse
    {
        [JsonPropertyName("cast")]        public string? Cast        { get; set; }
        [JsonPropertyName("temperature")] public double? Temperature { get; set; }
        [JsonPropertyName("tint")]        public double? Tint        { get; set; }
        [JsonPropertyName("saturation")]  public double? Saturation  { get; set; }
        [JsonPropertyName("noise")]       public string? Noise       { get; set; }
    }

    public class GeometryResponse
    {
        [JsonPropertyName("blur_type")]       public string? BlurType      { get; set; }
        [JsonPropertyName("blur_label")]      public string? BlurLabel     { get; set; }
        [JsonPropertyName("tilt_angle")]      public double? TiltAngle     { get; set; }
        [JsonPropertyName("tilt_label")]      public string? TiltLabel     { get; set; }
        [JsonPropertyName("tilt_confidence")] public double? TiltConfidence{ get; set; }
        [JsonPropertyName("moire_score")]     public double  MoireScore    { get; set; }
        [JsonPropertyName("moire_label")]     public string? MoireLabel    { get; set; }
    }

    public class IqaMetricItemDto
    {
        [JsonPropertyName("label")]     public string? Label     { get; set; }
        [JsonPropertyName("score")]     public double? Score     { get; set; }
        [JsonPropertyName("direction")] public string? Direction { get; set; }
        [JsonPropertyName("good_min")]  public double  GoodMin   { get; set; }
        [JsonPropertyName("good_max")]  public double  GoodMax   { get; set; }
        [JsonPropertyName("error")]     public string? Error     { get; set; }
    }

    public class CheckItemDto
    {
        [JsonPropertyName("name")]   public string? Name   { get; set; }
        [JsonPropertyName("passed")] public bool?   Passed { get; set; }
        [JsonPropertyName("value")]  public string? Value  { get; set; }
        [JsonPropertyName("needed")] public string? Needed { get; set; }
    }
}
