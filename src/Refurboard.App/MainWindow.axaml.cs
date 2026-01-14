using Avalonia.Controls;
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
}