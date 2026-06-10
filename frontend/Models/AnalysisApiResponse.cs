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

        // ── Hangi analizler çalıştı ───────────────────────────
        [JsonPropertyName("analysis")]       public AnalysisFlags? Analysis { get; set; }

        // ── DB kayıt ID'si (analyze yanıtında döner) ──────────
        [JsonPropertyName("saved_id")]       public int SavedId { get; set; }
    }

    public class AnalysisFlags
    {
        [JsonPropertyName("ai")]      public bool Ai      { get; set; } = true;
        [JsonPropertyName("quality")] public bool Quality { get; set; } = true;
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
        [JsonPropertyName("color_noise")]    public ColorNoiseResponse?  ColorNoise  { get; set; }

        [JsonPropertyName("iqa_metrics")]    public List<IqaMetricItemDto>? IqaMetrics  { get; set; }
        [JsonPropertyName("checks")]         public List<CheckItemDto>?  Checks      { get; set; }

        // Bölgesel haritalar — grid: List<List<double>>, değerler 0-100
        [JsonPropertyName("sharpness_map")]  public SharpnessMapDto?  SharpnessMap { get; set; }
        [JsonPropertyName("highlight_map")]  public HighlightMapDto?  HighlightMap { get; set; }
    }

    public class SharpnessMapDto
    {
        [JsonPropertyName("grid")]           public List<List<double>>? Grid         { get; set; }
        [JsonPropertyName("rows")]           public int                 Rows         { get; set; }
        [JsonPropertyName("cols")]           public int                 Cols         { get; set; }
        [JsonPropertyName("sharpest_cell")]  public List<int>?          SharpestCell { get; set; }
        [JsonPropertyName("softest_cell")]   public List<int>?          SoftestCell  { get; set; }
        [JsonPropertyName("global_score")]   public double              GlobalScore  { get; set; }
    }

    public class HighlightMapDto
    {
        [JsonPropertyName("grid")]           public List<List<double>>? Grid        { get; set; }
        [JsonPropertyName("rows")]           public int                 Rows        { get; set; }
        [JsonPropertyName("cols")]           public int                 Cols        { get; set; }
        [JsonPropertyName("worst_cell")]     public List<int>?          WorstCell   { get; set; }
        [JsonPropertyName("worst_pct")]      public double              WorstPct    { get; set; }
        [JsonPropertyName("has_critical")]   public bool                HasCritical { get; set; }
        [JsonPropertyName("global_pct")]     public double              GlobalPct   { get; set; }
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
        [JsonPropertyName("datetime")]     public string? Datetime    { get; set; }
        [JsonPropertyName("camera")]       public string? Camera      { get; set; }
        [JsonPropertyName("lens")]         public string? Lens        { get; set; }
        [JsonPropertyName("iso")]          public int?    Iso         { get; set; }
        [JsonPropertyName("aperture")]     public string? Aperture    { get; set; }
        [JsonPropertyName("shutter")]      public string? Shutter     { get; set; }
        [JsonPropertyName("focal_length")] public string? FocalLength { get; set; }
        [JsonPropertyName("flash")]        public bool?   Flash       { get; set; }
        [JsonPropertyName("has_gps")]      public bool?   HasGps      { get; set; }
    }

    public class ExposureResponse
    {
        [JsonPropertyName("label")]          public string? Label         { get; set; }
        [JsonPropertyName("highlight_clip")] public double  HighlightClip { get; set; }
        [JsonPropertyName("shadow_clip")]    public double  ShadowClip    { get; set; }
        [JsonPropertyName("dynamic_range")]  public double  DynamicRange  { get; set; }
        [JsonPropertyName("avg_brightness")] public double  AvgBrightness { get; set; }
        [JsonPropertyName("contrast_rms")]   public double? ContrastRms   { get; set; }
    }

    public class ColorResponse
    {
        [JsonPropertyName("cast")]              public string? Cast             { get; set; }
        [JsonPropertyName("cast_strength")]     public double? CastStrength     { get; set; }
        [JsonPropertyName("temperature")]       public double? Temperature      { get; set; }
        [JsonPropertyName("temperature_label")] public string? TemperatureLabel { get; set; }
        [JsonPropertyName("tint")]              public double? Tint             { get; set; }
        [JsonPropertyName("saturation")]        public double? Saturation       { get; set; }
        [JsonPropertyName("noise")]             public string? Noise            { get; set; }
    }

    public class ColorNoiseResponse
    {
        [JsonPropertyName("luma_noise")]   public double? LumaNoise   { get; set; }
        [JsonPropertyName("chroma_noise")] public double? ChromaNoise { get; set; }
        [JsonPropertyName("severity")]     public string? Severity    { get; set; }
        [JsonPropertyName("description")]  public string? Description { get; set; }
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
