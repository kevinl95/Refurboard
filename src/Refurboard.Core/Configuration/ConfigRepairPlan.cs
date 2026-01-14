namespace Refurboard.Core.Configuration;

public sealed record class ConfigRepairPlan(
    bool RewriteFile,
    bool TriggerCalibration,
    bool PromptForLocale,
    string Message)
{
    public static ConfigRepairPlan None { get; } = new(false, false, false, "Configuration validated successfully.");
}
