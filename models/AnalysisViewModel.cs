namespace TrueFrameUI.Models
{
    public class AnalysisViewModel
    {
        public string? ImagePath { get; set; }
        public bool RealFakeSelected { get; set; }
        public bool QualitySelected { get; set; }

        public int AiProbability { get; set; }
        public int RealProbability { get; set; }
        public int ConfidenceScore { get; set; }

        public int QualityScore { get; set; }
        public int Sharpness { get; set; }
        public int Contrast { get; set; }
        public int NoiseLevel { get; set; }
        public int Usability { get; set; }

        public string? Explanation { get; set; }
        public string? StatusMessage { get; set; }
    }
}