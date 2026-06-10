namespace TrueFrameUI.Models
{
    public class HistoryItemViewModel
    {
        public int     Id        { get; set; }
        public string  Name      { get; set; } = "";
        public string  Profile   { get; set; } = "";
        public double? Overall   { get; set; }
        public string  Verdict   { get; set; } = "";
        public string  Thumbnail { get; set; } = "";   // base64 data-uri
        public string  Label     { get; set; } = "";
        public double? FakeProb  { get; set; }
        public double? RealProb  { get; set; }
        public string  CreatedAt { get; set; } = "";
    }

    public class HistoryViewModel
    {
        public List<HistoryItemViewModel> Items    { get; set; } = new();
        public string?                    Warning  { get; set; }
        public string?                    Error    { get; set; }

        // Filtre durumu — form alanlarının seçili kalması için
        public string? FilterResult   { get; set; }   // ai | real | manip | uncertain
        public double? FilterMinScore { get; set; }
        public double? FilterMaxScore { get; set; }
        public string? FilterDateFrom { get; set; }   // YYYY-MM-DD
        public string? FilterDateTo   { get; set; }
        public string? FilterFileType { get; set; }   // jpg | png | webp | tiff | bmp
        public string? FilterQuery    { get; set; }
        public string? FilterProfile  { get; set; }   // none | web | social | print | news

        public bool HasActiveFilters =>
            !string.IsNullOrEmpty(FilterResult) || FilterMinScore.HasValue || FilterMaxScore.HasValue ||
            !string.IsNullOrEmpty(FilterDateFrom) || !string.IsNullOrEmpty(FilterDateTo) ||
            !string.IsNullOrEmpty(FilterFileType) || !string.IsNullOrEmpty(FilterQuery) ||
            !string.IsNullOrEmpty(FilterProfile);
    }
}
