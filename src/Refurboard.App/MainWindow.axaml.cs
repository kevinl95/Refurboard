using System;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Refurboard.App.ViewModels;
using Refurboard.Core.Configuration;

namespace Refurboard.App;

public partial class MainWindow : Window
{
    public MainWindow() : this(new MainWindowViewModel(ConfigBootstrapResult.Empty))
    {
    }

    public MainWindow(MainWindowViewModel viewModel)
    {
        InitializeComponent();
        DataContext = viewModel;
    }

    protected override async void OnOpened(EventArgs e)
    {
        base.OnOpened(e);
        if (DataContext is MainWindowViewModel viewModel)
        {
            await SafeExecuteAsync(() => viewModel.InitializeAsync());
        }
    }

    protected override async void OnClosed(EventArgs e)
    {
        if (DataContext is MainWindowViewModel viewModel)
        {
            await SafeExecuteAsync(() => viewModel.DisposeAsync().AsTask());
        }

        base.OnClosed(e);
    }

    private async void OnRestartCameraClicked(object? sender, RoutedEventArgs e)
    {
        if (DataContext is MainWindowViewModel viewModel)
        {
            await SafeExecuteAsync(() => viewModel.CameraPreview.RestartAsync());
        }
    }

    private static async Task SafeExecuteAsync(Func<Task> callback)
    {
        try
        {
            await callback().ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Camera pipeline error: {ex.Message}");
        }
    }
}