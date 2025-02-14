from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.style import Style
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.markdown import Markdown
from rich.box import DOUBLE
from rich.console import group
from datetime import datetime
import logging
import json
from typing import Dict, Any, List, Generator
from scraper import Scraper
from trade_up_calculator import TradeUpCalculator, TradeUpContract
import sys
import os
import time
import platform
import winreg
import subprocess
import re
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

class ConsoleUI:
    def __init__(self, config=None):
        self.console = Console()
        if config is None:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
        else:
            self.config = config
            
        self.logger = logging.getLogger(__name__)
        self.scraper = None
        self.calculator = None
        self.items_analyzed = 0
        self.running = True
        self._cleanup_in_progress = False  # Flag to prevent duplicate cleanup

    def show_welcome(self):
        """Display welcome message and instructions."""
        # Create title with gradient effect
        title = Text()
        title.append("✨ ", style="yellow")
        title.append("T", style="cyan")
        title.append("r", style="bright_cyan")
        title.append("a", style="blue")
        title.append("d", style="bright_blue")
        title.append("e", style="purple")
        title.append("U", style="bright_purple")
        title.append("p", style="magenta")
        title.append("T", style="bright_magenta")
        title.append("r", style="red")
        title.append("e", style="bright_red")
        title.append("n", style="yellow")
        title.append("d", style="bright_yellow")
        title.append("s", style="green")
        title.append(" ✨", style="bright_green")
        
        # Create subtitle with animation effect
        subtitle = Text("\n🎮 CS2 Market Analysis & Trade-Up Calculator", style="blue bold")
        
        # Create description
        description = Text(
            "\n🚀 Your advanced tool for market analysis and profitable trade-up discoveries",
            style="bright_blue"
        )
        
        # Create sections
        sections = [
            Text("\n📋 [bold yellow]Instructions[/bold yellow]", justify="left"),
            Text("1️⃣  Select a weapon by entering its index number", style="bright_white"),
            Text("2️⃣  Choose analysis type (market analysis or trade-up contracts)", style="bright_white"),
            Text("3️⃣  View results and statistics", style="bright_white"),
            Text("\n⌨️  [bold yellow]Commands[/bold yellow]", justify="left"),
            Text("• [cyan]exit[/cyan] - Quit the program", style="bright_white"),
            Text("• [cyan]back[/cyan] - Return to previous menu", style="bright_white"),
            Text("\n💡 [bold yellow]Pro Tips[/bold yellow]", justify="left"),
            Text("🔹 Use index numbers for quick selection", style="bright_white"),
            Text("🔹 Market analysis shows real-time prices", style="bright_white"),
            Text("🔹 Trade-up analysis finds best opportunities", style="bright_white"),
            Text("\n🛠️  [bold yellow]Features[/bold yellow]", justify="left"),
            Text("⭐ Real-time market data analysis", style="bright_white"),
            Text("⭐ Smart trade-up contract finder", style="bright_white"),
            Text("⭐ Profit margin calculator", style="bright_white")
        ]
        
        # Create main panel with all content
        main_panel = Panel(
            Align.center("\n".join(str(t) for t in [title, subtitle, description] + sections)),
            border_style="cyan",
            box=DOUBLE,
                padding=(1, 2),
            title="[bold cyan]🎮 Welcome to TradeUpTrends[/bold cyan]",
            subtitle="[bold blue]v1.0 Beta[/bold blue]"
        )
        
        self.console.print()
        self.console.print(main_panel)
        self.console.print()

    def initialize_components(self):
        """Initialize scraper and calculator components."""
        try:
            from temp import items_dict
            
            # Create progress bar with custom styling
            progress = Progress(
                SpinnerColumn("dots", style="cyan"),
                TextColumn("[bold cyan]{task.description}[/bold cyan]"),
                BarColumn(complete_style="green", finished_style="bright_green"),
                expand=True
            )
            
            # Show initialization progress
            with progress:
                task = progress.add_task("⚙️  Initializing components...", total=5)
                
                # Configure Chrome options
                chrome_options = uc.ChromeOptions()
                chrome_options.add_argument('--headless=new')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument('--log-level=3')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-popup-blocking')
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')

                progress.update(task, advance=1, description="🔍 Detecting Chrome installation...")
                
                # Get Chrome path for Windows
                if sys.platform == 'win32':
                    chrome_paths = [
                        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
                    ]
                    
                    for path in chrome_paths:
                        if os.path.exists(path):
                            chrome_options.binary_location = path
                            self.console.print(f"[dim]  ✓ Found Chrome at: {path}[/dim]")
                            break
                    else:
                        raise Exception("❌ Chrome browser not found. Please install Chrome.")
                    
                    progress.update(task, advance=1, description="📥 Setting up Chrome driver...")
            
            progress.update(task, advance=1, description="🔧 Testing driver...")
            
            try:
                # Get Chrome version from registry (Windows-specific)
                chrome_version = None
                major_version = None
                
                try:
                    if sys.platform == 'win32':
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon") as key:
                            chrome_version = winreg.QueryValueEx(key, "version")[0]
                            self.console.print(f"[dim]  ✓ Detected Chrome version from registry: {chrome_version}[/dim]")
                            major_version = int(chrome_version.split('.')[0])
                except Exception as e:
                    self.logger.warning(f"Failed to get Chrome version from registry: {str(e)}")
                
                progress.update(task, advance=1, description="🔧 Testing driver...")
                
                # Initialize WebDriver with undetected-chromedriver
                try:
                    if major_version:
                        self.driver = uc.Chrome(
                            options=chrome_options,
                            version_main=major_version,
                            headless=True,
                            use_subprocess=True
                        )
                    else:
                        self.driver = uc.Chrome(
                            options=chrome_options,
                            headless=True,
                            use_subprocess=True
                        )
                    
                    self.driver.set_page_load_timeout(30)
                    self.driver.get('about:blank')
                    time.sleep(0.5)
                    
                except Exception as e:
                    if hasattr(self, 'driver'):
                        try:
                            self.driver.quit()
                        except:
                            pass
                    raise Exception(f"Failed to initialize Chrome driver: {str(e)}")
                
                progress.update(task, advance=1, description="🔄 Initializing components...")
                
                # Initialize components with the existing driver
                self.scraper = Scraper(
                    url=self.config['scraping']['steam_market']['base_url'],
                    items_dict=items_dict,
                    driver=self.driver
                )
                
                self.calculator = TradeUpCalculator(self.config)
                
                progress.update(task, advance=1, description="✨ Initialization complete!")
                time.sleep(0.5)  # Small delay for visual effect
                
            except Exception as e:
                # Clean up if initialization fails
                if hasattr(self, 'driver'):
                    try:
                        self.driver.quit()
                    except:
                        pass
                
                # Provide more detailed error information
                error_msg = str(e)
                if "WinError 193" in error_msg:
                    # Get system architecture
                    is_64bits = platform.machine().endswith('64')
                    error_msg = (
                        f"Chrome driver architecture mismatch. Your system is "
                        f"{'64-bit' if is_64bits else '32-bit'}. "
                        f"Chrome version: {chrome_version or 'Unknown'}. "
                        f"Please ensure both Chrome and its driver are 64-bit versions."
                    )
                elif "session not created" in error_msg.lower():
                    error_msg = (
                        f"Chrome version mismatch. Your Chrome version: {chrome_version or 'Unknown'}. "
                        f"Please update Chrome to the latest version."
                    )
                raise Exception(f"Chrome driver setup failed: {error_msg}")
            
            # Show success message
            self.console.print()
            self.console.print(Panel(
                "[bold green]✨ All components initialized successfully![/bold green]",
                border_style="green",
                box=DOUBLE,
                padding=(1, 2)
            ))
            self.console.print()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {str(e)}")
            
            # Show error panel with better formatting and more specific troubleshooting
            error_text = [
                "[bold red]⚠️  Initialization Failed[/bold red]",
                "",
                "[bold yellow]Details:[/bold yellow]",
                f"[red dim]{str(e)}[/red dim]",
                "",
                "[bold cyan]Troubleshooting Tips:[/bold cyan]",
                "[green]✓[/green] Verify Chrome is installed and up to date",
                "[green]✓[/green] Ensure Chrome version matches your system architecture (32/64-bit)",
                "[yellow]🔑[/yellow] Try running as administrator",
                "[blue]🛡️[/blue] Temporarily disable antivirus",
                "[cyan]🌐[/cyan] Check internet connection",
                "[magenta]🔄[/magenta] Restart your computer",
                "",
                "[dim italic]If the problem persists, please report this error with your system details.[/dim italic]"
            ]
            
            error_panel = Panel(
                "\n".join(error_text),
                border_style="red",
                box=DOUBLE,
                padding=(1, 2),
                title="[bold red]❌ Error[/bold red]",
                subtitle="Need help? Visit our support page"
            )
            
            self.console.print()
            self.console.print(error_panel)
            self.console.print()
            return False

    def __del__(self):
        """Clean up resources when the object is destroyed."""
        if not self._cleanup_in_progress:
            self.cleanup()

    def cleanup(self):
        """Clean up resources safely."""
        self._cleanup_in_progress = True
        try:
            if hasattr(self, 'driver'):
                try:
                    self.driver.close()
                    time.sleep(0.5)  # Brief pause to allow cleanup
                    self.driver.quit()
                except Exception as e:
                    self.logger.debug(f"Driver cleanup error (safe to ignore): {str(e)}")
                finally:
                    self.driver = None
        except Exception as e:
            self.logger.debug(f"Final cleanup error (safe to ignore): {str(e)}")
        finally:
            self._cleanup_in_progress = False

    def display_weapon_selection(self, weapons: Dict[str, str]) -> str:
        """Display weapon selection menu and get user choice."""
        weapons_list = list(weapons.keys())
        
        # Create weapon selection layout with multiple tables
        categories = {
            "Pistol": ["glock", "usp", "p250", "deagle", "fiveseven", "tec9", "cz75", "revolver", "dualies"],
            "Rifle": ["ak", "m4a1", "m4a4", "aug", "sg553", "famas", "galilar", "awp", "scout", "scar20", "g3sg1"],
            "SMG": ["mp5", "mp7", "mp9", "mac10", "ppbizon", "p90", "ump45"],
            "Heavy": ["nova", "xm1014", "mag7", "sawedoff", "m249", "negev"]
        }
        
        # Category icons and colors
        category_styles = {
            "Pistol": ("🔫", "cyan"),
            "Rifle": ("🎯", "green"),
            "SMG": ("💨", "yellow"),
            "Heavy": ("💥", "red")
        }
        
        # Create a table for each category
        tables = []
        weapon_index = 1
        
        for category, weapons_in_cat in categories.items():
            icon, color = category_styles[category]
            
            table = Table(
                title=f"[bold {color}]{icon} {category}[/bold {color}]",
                box=DOUBLE,
                border_style=color,
                padding=(0, 2),
                collapse_padding=True,
                width=40
            )
            
            table.add_column("ID", style=f"bright_{color}", justify="center", width=4)
            table.add_column("Weapon", style="bright_white", width=20)
            table.add_column("Status", style=f"bright_{color}", justify="center", width=10)
            
            # Add weapons for this category
            for weapon in weapons_list:
                if weapon in weapons_in_cat:
                    status = "[green]✓[/green]"
                    table.add_row(
                        f"[{color}]{weapon_index}[/{color}]",
                        weapon.upper(),
                        status
                    )
                    weapon_index += 1
            
            tables.append(table)
        
        # Create a layout with two columns of tables
        layout = Table.grid(padding=2)
        layout.add_column("Left", justify="center")
        layout.add_column("Right", justify="center")
        
        # Add tables to layout in pairs
        for i in range(0, len(tables), 2):
            row = [tables[i]]
            if i + 1 < len(tables):
                row.append(tables[i + 1])
            else:
                row.append("")  # Empty cell for odd number of tables
            layout.add_row(*row)
        
        # Create selection panel with enhanced layout
        @group()
        def create_menu():
            yield layout
            yield Text("")  # Empty line for spacing
            yield Text("[bold yellow]Navigation:[/bold yellow]")
            yield Text("🔹 [cyan]Enter number (1-35)[/cyan] or [cyan]weapon name[/cyan] to select")
            yield Text("🔹 Type [red]'exit'[/red] to quit")
            yield Text("🔹 Type [yellow]'back'[/yellow] to return")
            yield Text("")
            yield Text("[bold yellow]Quick Filters:[/bold yellow]")
            yield Text("🔹 Type [cyan]'p'[/cyan] for Pistols")
            yield Text("🔹 Type [cyan]'r'[/cyan] for Rifles")
            yield Text("🔹 Type [cyan]'s'[/cyan] for SMGs")
            yield Text("🔹 Type [cyan]'h'[/cyan] for Heavy Weapons")
        
        selection_panel = Panel(
            create_menu(),
            title="[bold cyan]🎯 Weapon Selection[/bold cyan]",
            subtitle="[blue]Select a weapon to analyze[/blue]",
            border_style="cyan",
            box=DOUBLE,
            padding=(1, 2)
        )

        self.console.print()
        self.console.print(selection_panel)
        
        while True:
            choice = Prompt.ask("\n[cyan]Select weapon[/cyan]").lower()
            
            if choice == 'exit':
                    return None
            elif choice == 'back':
                return None
            # Quick filters
            elif choice in ['p', 'r', 's', 'h']:
                filter_map = {
                    'p': 'Pistol',
                    'r': 'Rifle',
                    's': 'SMG',
                    'h': 'Heavy'
                }
                filtered_weapons = [w for w in weapons_list 
                                 if next((cat for cat, weapons in categories.items() 
                                        if w in weapons), "Other") == filter_map[choice]]
                if filtered_weapons:
                    self.console.print(f"\n[cyan]Available {filter_map[choice]}s:[/cyan]")
                    for i, w in enumerate(filtered_weapons, 1):
                        self.console.print(f"  {i}. {w.upper()}")
                continue

            try:
                if choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(weapons_list):
                        return weapons_list[index]
                else:
                    if choice in weapons_list:
                        return choice
                        
                self.console.print("[red]❌ Invalid selection. Please try again.[/red]")
            except ValueError:
                self.console.print("[red]❌ Invalid input. Please enter a number or weapon name.[/red]")

    def display_analysis_menu(self) -> str:
        """Display analysis type selection menu."""
        menu_panel = Panel(
            "\n".join([
                "[bold cyan]Choose Analysis Type:[/bold cyan]",
                "",
                "[cyan]1.[/cyan] 📊 [bold white]Market Analysis[/bold white]",
                "   [dim]• Real-time price tracking[/dim]",
                "   [dim]• Market trends and statistics[/dim]",
                "   [dim]• Price distribution analysis[/dim]",
                "",
                "[cyan]2.[/cyan] 💹 [bold white]Trade-Up Contracts[/bold white]",
                "   [dim]• Profitable trade-up finder[/dim]",
                "   [dim]• Risk assessment[/dim]",
                "   [dim]• ROI calculator[/dim]",
                "",
                "[yellow]Enter your choice (1-2)[/yellow]"
            ]),
            title="[bold cyan]🎯 Analysis Options[/bold cyan]",
            border_style="cyan",
            box=DOUBLE,
            padding=(1, 2)
        )
        
        self.console.print()
        self.console.print(menu_panel)
        
        while True:
            choice = Prompt.ask("\n[cyan]Select option[/cyan]")
            
            if choice == 'exit':
                return None
            elif choice == '1':
                return 'market'
            elif choice == '2':
                return 'trade-up'
            else:
                self.console.print("[red]❌ Invalid choice. Please enter 1 or 2.[/red]")

    def get_analysis_options(self) -> Dict[str, Any]:
        """Get analysis options from user."""
        options = {}
        
        # Create options panel
        options_panel = Panel(
            "\n".join([
                "[bold cyan]Analysis Options[/bold cyan]",
                "",
                "🌐 [bold white]VPN Settings[/bold white]",
                "   Enable VPN for scraping (recommended for large analyses)",
                "",
                "📄 [bold white]Page Settings[/bold white]",
                "   Set maximum pages to analyze (0 for all pages)",
                "",
                "💰 [bold white]Price Filters[/bold white]",
                "   Set minimum and maximum price filters",
                "",
                "⚙️  [bold white]Other Options[/bold white]",
                "   Additional analysis settings"
            ]),
            title="[bold cyan]⚙️ Configure Analysis[/bold cyan]",
            border_style="cyan",
            box=DOUBLE,
            padding=(1, 2)
        )
        
        self.console.print()
        self.console.print(options_panel)
        
        # Get VPN preference
        options['use_vpn'] = Confirm.ask("\n[cyan]Enable VPN for analysis?[/cyan]", default=False)
        
        # Get page limit
        while True:
            try:
                page_limit = IntPrompt.ask(
                    "\n[cyan]Maximum pages to analyze (0 for all pages)[/cyan]",
                    default=0
                )
                if page_limit >= 0:
                    options['page_limit'] = page_limit
                    break
                self.console.print("[red]Please enter a non-negative number.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a valid number.[/red]")
        
        # Get price range
        while True:
            try:
                min_price = float(Prompt.ask(
                    "\n[cyan]Minimum price filter (USD)[/cyan]",
                    default="0.0"
                ))
                if min_price >= 0:
                    options['min_price'] = min_price
                    break
                self.console.print("[red]Please enter a non-negative number.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a valid number.[/red]")
        
        while True:
            try:
                max_price = float(Prompt.ask(
                    "\n[cyan]Maximum price filter (USD)[/cyan]",
                    default="1000.0"
                ))
                if max_price > min_price:
                    options['max_price'] = max_price
                    break
                self.console.print("[red]Maximum price must be greater than minimum price.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a valid number.[/red]")
        
        # Confirm options
        self.console.print("\n[bold cyan]Selected Options:[/bold cyan]")
        self.console.print(f"• VPN Enabled: [{'green' if options['use_vpn'] else 'red'}]{options['use_vpn']}[/]")
        self.console.print(f"• Page Limit: [yellow]{options['page_limit']} {'(All Pages)' if options['page_limit'] == 0 else 'pages'}[/]")
        self.console.print(f"• Price Range: [green]${options['min_price']} - ${options['max_price']}[/]")
        
        return options

    def display_results(self, items: List[Dict[str, Any]]):
        """Display analysis results."""
        if not items:
            self.console.print(Panel(
                "[yellow]No items found for analysis![/yellow]",
                title="[bold yellow]⚠️ Warning[/bold yellow]",
                border_style="yellow",
                box=DOUBLE
            ))
            return

        self.items_analyzed += len(items)
        
        # Calculate statistics
        prices = [float(item["price"].replace("$", "").replace(",", "")) for item in items]
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        median_price = sorted(prices)[len(prices)//2]
        
        # Create summary panel
        summary = Panel(
            "\n".join([
                "[bold cyan]📊 Market Statistics[/bold cyan]",
                "",
                f"[bright_white]Total Items:[/bright_white] [cyan]{len(items)}[/cyan]",
                f"[bright_white]Average Price:[/bright_white] [green]${avg_price:.2f}[/green]",
                f"[bright_white]Median Price:[/bright_white] [green]${median_price:.2f}[/green]",
                f"[bright_white]Price Range:[/bright_white] [green]${min_price:.2f}[/green] - [green]${max_price:.2f}[/green]",
                "",
                "[dim]• Prices are in USD[/dim]",
                "[dim]• Data is real-time from Steam Market[/dim]"
            ]),
            title="[bold cyan]📈 Market Analysis[/bold cyan]",
            border_style="cyan",
            box=DOUBLE,
            padding=(1, 2)
        )
        
        # Create items table
        table = Table(
            title="[bold cyan]🎮 Market Items[/bold cyan]",
            box=DOUBLE,
            border_style="cyan",
            header_style="bold cyan",
            padding=(0, 1)
        )
        
        table.add_column("Name", style="bright_white")
        table.add_column("Price", style="green", justify="right")
        table.add_column("Wear", style="bright_blue")
        table.add_column("StatTrak", justify="center", style="bright_magenta")
        table.add_column("Souvenir", justify="center", style="bright_yellow")
        table.add_column("Trend", justify="center", style="bright_cyan")
        
        # Sort items by price
        sorted_items = sorted(items, key=lambda x: float(x["price"].replace("$", "").replace(",", "")))
        
        for item in sorted_items:
            price_float = float(item["price"].replace("$", "").replace(",", ""))
            trend = "↗️" if price_float > avg_price else "↘️" if price_float < avg_price else "➡️"
            
            table.add_row(
                item["name"],
                f"[bold green]${price_float:.2f}[/bold green]",
                item.get("wear", "N/A"),
                "✨" if item["stat"] else "❌",
                "🏆" if item["souv"] else "❌",
                trend
            )
        
        # Display everything
        self.console.print()
        self.console.print(summary)
        self.console.print()
        self.console.print(table)
        self.console.print()
        
        # Add tips panel
        tips_panel = Panel(
            "\n".join([
                "[bright_white]• Use arrow keys to scroll through items[/bright_white]",
                "[bright_white]• Press 'Ctrl+C' to copy item data[/bright_white]",
                "[bright_white]• Items are sorted by price for easy comparison[/bright_white]"
            ]),
            title="[bold yellow]💡 Tips[/bold yellow]",
            border_style="yellow",
            box=DOUBLE,
            padding=(1, 1)
        )
        self.console.print(tips_panel)
        self.console.print()

    def display_trade_up_opportunities(self, opportunities: List[TradeUpContract]):
        """Display trade-up contract opportunities."""
        if not opportunities:
            self.console.print(Panel(
                "[yellow]No profitable trade-up opportunities found![/yellow]\n" +
                "[dim]Try adjusting your search criteria or analyzing different items.[/dim]",
                title="[bold yellow]⚠️ No Opportunities[/bold yellow]",
                border_style="yellow",
                box=DOUBLE
            ))
            return

        # Create summary panel
        summary = Panel(
            "\n".join([
                "[bold cyan]📊 Trade-Up Analysis[/bold cyan]",
                "",
                f"[bright_white]Found Opportunities:[/bright_white] [cyan]{len(opportunities)}[/cyan]",
                f"[bright_white]Best Profit Margin:[/bright_white] [green]{max(o.profit_margin for o in opportunities):+.1f}%[/green]",
                f"[bright_white]Average ROI:[/bright_white] [green]{sum(o.profit_margin for o in opportunities)/len(opportunities):+.1f}%[/green]",
                "",
                "[dim]• All calculations include Steam Market fees[/dim]",
                "[dim]• Risk levels are based on historical data[/dim]"
            ]),
            title="[bold cyan]💹 Trade-Up Summary[/bold cyan]",
            border_style="cyan",
            box=DOUBLE,
            padding=(1, 2)
        )
        
        # Create opportunities table
        table = Table(
            title="[bold cyan]🎯 Trade-Up Opportunities[/bold cyan]",
            box=DOUBLE,
            border_style="cyan",
            header_style="bold cyan",
            padding=(0, 1)
        )
        
        table.add_column("Input Items", style="bright_white")
        table.add_column("Potential Outputs", style="bright_green")
        table.add_column("Cost", justify="right", style="bright_blue")
        table.add_column("Expected Value", justify="right", style="bright_cyan")
        table.add_column("Profit", justify="right", style="bright_magenta")
        table.add_column("Risk", justify="center", style="bright_yellow")
        table.add_column("ROI", justify="center", style="bright_green")
        
        # Sort opportunities by profit margin
        sorted_opps = sorted(opportunities, key=lambda x: x.profit_margin, reverse=True)
        
        for contract in sorted_opps:
            # Format input items
            input_names = ", ".join(item["name"].split("|")[1].strip() 
                                  for item in contract.input_items[:3])
            if len(contract.input_items) > 3:
                input_names += f" [dim]+{len(contract.input_items)-3} more[/dim]"

            # Format output items
            output_names = ", ".join(item["name"].split("|")[1].strip() 
                                   for item in contract.potential_outputs[:2])
            if len(contract.potential_outputs) > 2:
                output_names += f" [dim]+{len(contract.potential_outputs)-2} more[/dim]"
            
            # Get risk emoji
            risk_emoji = {
                "Low Risk": "🟢",
                "Medium Risk": "🟡",
                "High Risk": "🔴"
            }.get(contract.risk_level, "⚪")

            table.add_row(
                input_names,
                output_names,
                f"[bold blue]${contract.cost:.2f}[/bold blue]",
                f"[bold cyan]${contract.expected_value:.2f}[/bold cyan]",
                f"[bold magenta]{contract.profit_margin:+.1f}%[/bold magenta]",
                f"{risk_emoji} {contract.risk_level}",
                f"[{'green' if contract.profit_margin > 0 else 'red'}]" +
                f"{'↗️' if contract.profit_margin > 0 else '↘️'} " +
                f"{abs(contract.profit_margin):.1f}%[/]"
            )
        
        # Display everything
        self.console.print()
        self.console.print(summary)
        self.console.print()
        self.console.print(table)
        self.console.print()
        
        # Add tips panel
        tips_panel = Panel(
            "\n".join([
                "[bright_white]• Green arrows (↗️) indicate profitable opportunities[/bright_white]",
                "[bright_white]• Risk levels: 🟢 Low, 🟡 Medium, 🔴 High[/bright_white]",
                "[bright_white]• Click on any row to see detailed contract information[/bright_white]"
            ]),
            title="[bold yellow]💡 Tips[/bold yellow]",
            border_style="yellow",
            box=DOUBLE,
            padding=(1, 1)
        )
        self.console.print(tips_panel)
        self.console.print()

    def run(self):
        """Main program loop."""
        try:
            self.show_welcome()
            
            if not self.initialize_components():
                return

            while self.running:
                try:
                    # Show main menu
                    choice = self.display_main_menu()
                    if not choice:
                        break
                        
                    if choice == 'analyze':
                        self.run_analysis()
                    elif choice == 'settings':
                        self.show_settings()
                    elif choice == 'help':
                        self.show_help()
                    elif choice == 'about':
                        self.show_about()
                    elif choice == 'exit':
                        break

                except KeyboardInterrupt:
                    self.console.print("\nOperation cancelled by user.")
                    break
                except Exception as e:
                    self.logger.exception("Error during operation")
                    self.console.print(f"[red]Error: {str(e)}[/red]")
                    if not Prompt.ask("\nContinue?", choices=['y', 'n']) == 'y':
                        break

        except Exception as e:
            self.logger.exception("Fatal error occurred")
            self.console.print(f"[bold red]Fatal Error: {str(e)}[/bold red]")
        finally:
            # Show goodbye message with style
            self.show_goodbye()
            # Clean up resources
            self.cleanup()

    def display_main_menu(self) -> str:
        """Display the main menu and get user choice."""
        # Create menu with options
        menu_items = [
            ("🔍 Analyze", "Start market analysis or find trade-up opportunities"),
            ("⚙️  Settings", "Configure application settings"),
            ("❓ Help", "View help documentation and guides"),
            ("ℹ️  About", "View application information"),
            ("🚪 Exit", "Exit the application")
        ]
        
        # Create menu table
        table = Table(
            title="[bold cyan]🎮 Main Menu[/bold cyan]",
            box=DOUBLE,
            border_style="cyan",
            header_style="bold cyan",
            padding=(0, 1),
            show_lines=True
        )
        
        table.add_column("Option", style="bright_cyan", width=15)
        table.add_column("Description", style="bright_white", width=50)
        
        for option, description in menu_items:
            table.add_row(option, description)
        
        # Create menu panel
        @group()
        def create_menu():
            yield table
            yield Text("")
            yield Text("[bold yellow]Navigation:[/bold yellow]")
            yield Text("🔹 Type the [cyan]first letter[/cyan] or [cyan]full name[/cyan] of an option")
            yield Text("🔹 Press [red]'Ctrl+C'[/red] to exit at any time")
            yield Text("")
            yield Text("[bold yellow]Quick Commands:[/bold yellow]")
            yield Text("🔹 [cyan]'a'[/cyan] or [cyan]'analyze'[/cyan] - Start analysis")
            yield Text("🔹 [cyan]'s'[/cyan] or [cyan]'settings'[/cyan] - Open settings")
            yield Text("🔹 [cyan]'h'[/cyan] or [cyan]'help'[/cyan] - View help")
            yield Text("🔹 [cyan]'i'[/cyan] or [cyan]'about'[/cyan] - View info")
            yield Text("🔹 [cyan]'e'[/cyan] or [cyan]'exit'[/cyan] - Exit")
        
        menu_panel = Panel(
            create_menu(),
            title="[bold cyan]🎯 TradeUpTrends[/bold cyan]",
            subtitle="[blue]Choose an option to continue[/blue]",
            border_style="cyan",
            box=DOUBLE,
            padding=(1, 2)
        )
        
        self.console.print()
        self.console.print(menu_panel)
        
        # Get user choice
        while True:
            choice = Prompt.ask("\n[cyan]Select option[/cyan]").lower()
            
            # Map single letters to full commands
            choice_map = {
                'a': 'analyze',
                's': 'settings',
                'h': 'help',
                'i': 'about',
                'e': 'exit'
            }
            
            # Convert single letter to full command if needed
            if choice in choice_map:
                choice = choice_map[choice]
            
            if choice in ['analyze', 'settings', 'help', 'about', 'exit']:
                return choice
            else:
                self.console.print("[red]❌ Invalid choice. Please try again.[/red]")

    def run_analysis(self):
        """Run the analysis workflow."""
        while True:
            try:
                # Get weapon selection
                weapons_list = list(self.scraper.items_dict.keys())
                weapon = self.display_weapon_selection(self.scraper.items_dict)
                if not weapon:
                    break
                    
                # Get analysis type
                analysis_type = self.display_analysis_menu()
                if not analysis_type:
                    break
                
                # Get analysis options
                options = self.get_analysis_options()
                
                # Configure scraper with options
                self.scraper.use_vpn = options['use_vpn']
                if self.scraper.use_vpn:
                    self.scraper._init_vpn()
                
                # Update config with options
                self.config['analysis']['price_limits']['min_price_usd'] = options['min_price']
                self.config['analysis']['price_limits']['max_price_usd'] = options['max_price']
                self.config['performance']['limits']['max_pages_per_request'] = options['page_limit']
                
                # Clear the console before starting analysis
                self.console.clear()
                
                # Perform analysis
                self.console.print(f"\n[cyan]Analyzing {self.scraper.items_dict[weapon]}...[/cyan]")
                
                try:
                    with self.console.status(f"[cyan]Analyzing {self.scraper.items_dict[weapon]}...[/cyan]") as status:
                        items = list(self.scraper.get_items(weapon))
                        
                        # Filter items by price
                        items = [item for item in items 
                                if options['min_price'] <= float(item['price'].replace('$', '').replace(',', '')) <= options['max_price']]
                        
                        if analysis_type == 'market':
                            self.display_results(items)
                        else:  # trade-up
                            opportunities = self.calculator.find_trade_up_opportunities(items)
                            self.display_trade_up_opportunities(opportunities)
                except Exception as e:
                    self.logger.error(f"Analysis failed: {str(e)}")
                    self.console.print(f"[red]Error during analysis: {str(e)}[/red]")

                # Ask to continue
                if not Prompt.ask("\nAnalyze another weapon?", choices=['y', 'n']) == 'y':
                    break

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Operation cancelled by user[/yellow]")
                break
            except Exception as e:
                self.logger.error(f"Error during analysis: {str(e)}")
                self.console.print(f"[red]Error: {str(e)}[/red]")
                if not Prompt.ask("\nContinue?", choices=['y', 'n']) == 'y':
                    break

    def show_settings(self):
        """Show settings menu."""
        settings_panel = Panel(
            "\n".join([
                "[bold cyan]Application Settings[/bold cyan]",
                "",
                "[cyan]1.[/cyan] 🌐 Network Settings",
                "   [dim]• Configure proxy and VPN settings[/dim]",
                "   [dim]• Adjust request timeouts and delays[/dim]",
                "",
                "[cyan]2.[/cyan] 📊 Analysis Settings",
                "   [dim]• Set price range limits[/dim]",
                "   [dim]• Configure trade-up parameters[/dim]",
                "",
                "[cyan]3.[/cyan] 🎨 UI Settings",
                "   [dim]• Customize appearance[/dim]",
                "   [dim]• Adjust display options[/dim]",
                "",
                "[cyan]4.[/cyan] 📝 Logging Settings",
                "   [dim]• Set log levels[/dim]",
                "   [dim]• Configure log file options[/dim]",
                "",
                "[yellow]Enter your choice (1-4) or 'back' to return[/yellow]"
            ]),
            title="[bold cyan]⚙️  Settings[/bold cyan]",
            subtitle="[blue]Configure application settings[/blue]",
            border_style="cyan",
            box=DOUBLE,
            padding=(1, 2)
        )
        
        self.console.print()
        self.console.print(settings_panel)
        
        while True:
            choice = Prompt.ask("\n[cyan]Select option[/cyan]").lower()
            if choice == 'back':
                break
            elif choice in ['1', '2', '3', '4']:
                self.console.print("[yellow]Settings functionality coming soon![/yellow]")
            else:
                self.console.print("[red]❌ Invalid choice. Please enter 1-4 or 'back'.[/red]")

    def show_about(self):
        """Show about information."""
        about_text = [
            "[bold cyan]🎮 TradeUpTrends[/bold cyan]",
            "",
            "[bright_white]Version:[/bright_white] [cyan]1.0 Beta[/cyan]",
            "[bright_white]Author:[/bright_white] [cyan]Your Name[/cyan]",
            "[bright_white]License:[/bright_white] [cyan]MIT[/cyan]",
            "",
            "[bold yellow]Description:[/bold yellow]",
            "TradeUpTrends is an advanced tool for CS2 market analysis and trade-up contract optimization.",
            "It provides real-time market data analysis and helps find profitable trade-up opportunities.",
            "",
            "[bold yellow]Features:[/bold yellow]",
            "• Real-time market data analysis",
            "• Smart trade-up contract finder",
            "• Profit margin calculator",
            "• Advanced statistical analysis",
            "",
            "[bold yellow]Technologies:[/bold yellow]",
            "• Python 3.11+",
            "• Selenium WebDriver",
            "• Rich TUI Framework",
            "• Steam Market API",
            "",
            "[dim italic]Press Enter to return to main menu[/dim italic]"
        ]
        
        about_panel = Panel(
            "\n".join(about_text),
            title="[bold cyan]ℹ️  About TradeUpTrends[/bold cyan]",
            border_style="cyan",
            box=DOUBLE,
            padding=(1, 2)
        )
        
        self.console.print()
        self.console.print(about_panel)
        self.console.input()

    def show_goodbye(self):
        """Show a stylish goodbye message."""
        goodbye_text = [
            "[bold cyan]👋 Thanks for using TradeUpTrends![/bold cyan]",
            "",
            "[bright_white]We hope you found some profitable opportunities![/bright_white]",
            "",
            "[yellow]See you next time! 🚀[/yellow]"
        ]
        
        goodbye_panel = Panel(
            "\n".join(goodbye_text),
            border_style="cyan",
            box=DOUBLE,
            padding=(1, 2)
        )
        
        self.console.print()
        self.console.print(goodbye_panel)
        self.console.print()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ui = ConsoleUI()
    ui.run() 