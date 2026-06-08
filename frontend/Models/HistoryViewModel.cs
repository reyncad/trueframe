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
    }
}
