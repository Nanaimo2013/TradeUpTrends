from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import print as rprint
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.columns import Columns
from rich.style import Style
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from trade_up_calculator import TradeUpContract
import time
import keyboard

logger = logging.getLogger(__name__)

class ConsoleUI:
    def __init__(self):
        self.console = Console()
        with open('config.json', 'r') as f:
            self.config = json.load(f)
        self.layout = self._create_layout()
        self.items_analyzed = 0
        self.current_menu = "main"
        self.selected_index = 0
        self.live = None
        self.running = True
        self.last_key_time = 0
        self.key_cooldown = 0.15  # Cooldown between key presses
        self.scraper = None
        self.calculator = None
        
    def _create_layout(self) -> Layout:
        """Create the main layout for the application."""
        layout = Layout(name="root")
        
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="content", ratio=2),
            Layout(name="sidebar", ratio=1),
        )
        
        return layout

    def run(self):
        """Main UI loop."""
        self.show_welcome(first_time=True)
        
        # Set up static UI elements once
        self.layout["header"].update(self._create_header())
        self.layout["footer"].update(self._create_footer())
        
        with Live(self.layout, refresh_per_second=self.config['ui']['refresh_rate'], screen=True) as live:
            self.live = live
            while self.running:
                self._handle_input()
                time.sleep(0.05)  # Reduce CPU usage

    def _handle_input(self):
        """Handle keyboard input."""
        current_time = time.time()
        
        if current_time - self.last_key_time < self.key_cooldown:
            return
            
        if keyboard.is_pressed('up'):
            self.selected_index = max(0, self.selected_index - 1)
            self.last_key_time = current_time
            self._update_display()
        elif keyboard.is_pressed('down'):
            menu_items = self.config['ui']['display']['menu'][self.current_menu]
            self.selected_index = min(len(menu_items) - 1, self.selected_index + 1)
            self.last_key_time = current_time
            self._update_display()
        elif keyboard.is_pressed('enter'):
            self._handle_menu_selection()
            self.last_key_time = current_time
            self._update_display()
        elif keyboard.is_pressed('esc'):
            if self.current_menu == "main":
                self.running = False
            else:
                self.current_menu = "main"
                self.selected_index = 0
            self.last_key_time = current_time
            self._update_display()

    def _handle_menu_selection(self):
        """Handle menu item selection."""
        menu_items = self.config['ui']['display']['menu'][self.current_menu]
        selected_item = menu_items[self.selected_index]
        
        if self.current_menu == "main":
            if selected_item == "Exit":
                self.running = False
            elif selected_item == "Settings":
                self.current_menu = "settings"
                self.selected_index = 0
            elif selected_item == "Analyze Market":
                self._analyze_market()
            elif selected_item == "Find Trade-Up Contracts":
                self._find_trade_up_contracts()
            elif selected_item == "Help":
                self.show_help()
        elif self.current_menu == "settings":
            if selected_item == "Back to Main Menu":
                self.current_menu = "main"
                self.selected_index = 0

    def _create_menu_panel(self) -> Panel:
        """Create the menu panel with highlighted selection."""
        menu_items = self.config['ui']['display']['menu'][self.current_menu]
        menu_text = []
        
        for i, item in enumerate(menu_items):
            if i == self.selected_index:
                style = self.config['ui']['color_scheme']['menu_selected']
                menu_text.append(f"[{style}]> {item}[/{style}]")
            else:
                style = self.config['ui']['color_scheme']['menu_unselected']
                menu_text.append(f"[{style}]  {item}[/{style}]")
        
        return Panel(
            "\n".join(menu_text),
            title=f"{self.current_menu.title()} Menu",
            border_style=self.config['ui']['color_scheme']['primary']
        )

    def _update_display(self):
        """Update only the dynamic parts of the display."""
        if self.live:
            # Only update the menu content and sidebar stats
            self.layout["content"].update(self._create_menu_panel())
            self.layout["sidebar"].update(self._create_stats_panel())

    def _create_header(self) -> Panel:
        """Create the header panel."""
        title = Text("TradeUpTrends", style=f"bold {self.config['ui']['color_scheme']['primary']}")
        subtitle = Text("CS2 Market Analysis Tool", style=f"italic {self.config['ui']['color_scheme']['secondary']}")
        
        return Panel(
            title + "\n" + subtitle,
            border_style=self.config['ui']['color_scheme']['primary'],
            padding=(1, 2),
            title="Welcome"
        )

    def show_welcome(self, first_time=False):
        """Display welcome message and main menu."""
        if first_time:
            # Set up initial static elements
            title = Text("TradeUpTrends", style=f"bold {self.config['ui']['color_scheme']['primary']}")
            subtitle = Text("CS2 Market Analysis Tool", style=f"italic {self.config['ui']['color_scheme']['secondary']}")
            
            header_content = Panel(
                title + "\n" + subtitle,
                border_style=self.config['ui']['color_scheme']['primary'],
                padding=(1, 2),
                title="Welcome"
            )
            
            self.layout["header"].update(header_content)
            self.layout["footer"].update(self._create_footer())
            
            # Update dynamic elements
            self.layout["content"].update(self._create_menu_panel())
            self.layout["sidebar"].update(self._create_stats_panel())
            
            # Wait for user to press enter
            self.console.print("\n[cyan]Press Enter to start...[/cyan]")
            keyboard.wait('enter')
        else:
            self._update_display()

    def _create_stats_panel(self) -> Panel:
        """Create a panel showing current market statistics."""
        table = Table(show_header=False, padding=(0, 1))
        table.add_row("Session Start", datetime.now().strftime("%Y-%m-%d %H:%M"))
        table.add_row("Items Analyzed", str(self.items_analyzed))
        table.add_row("Market Status", "[green]Online[/green]")
        
        return Panel(
            table,
            title="Statistics",
            border_style="cyan",
            padding=(1, 2)
        )

    def _create_footer(self) -> Panel:
        """Create the footer panel."""
        controls = [
            "[blue]↑/↓[/blue]: Navigate",
            "[blue]Enter[/blue]: Select",
            "[blue]Esc[/blue]: Back/Exit"
        ]
        return Panel(
            Text(" | ".join(controls), justify="center"),
            border_style=self.config['ui']['color_scheme']['primary']
        )

    def get_weapon_selection(self, weapons: Dict[str, str]) -> str:
        """Display weapon selection menu and get user choice."""
        table = Table(
            title="Available Weapons",
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
            title_style="bold cyan"
        )
        
        table.add_column("Index", style="cyan", justify="right")
        table.add_column("Weapon", style="green")
        table.add_column("Market Items", style="yellow")
        table.add_column("Price Range", style="blue")
        
        for i, weapon in enumerate(weapons.keys(), 1):
            table.add_row(
                str(i),
                weapon.upper(),
                "Loading...",
                "$ 0.03 - 1000.00"
            )

        # Update the content using existing live context
        self.layout["content"].update(Panel(table, title="Weapon Selection"))
        
        # Temporarily suspend live display for input
        if self.live:
            self.live.stop()
        
        choice = Prompt.ask(
            "\nSelect weapon by name",
            choices=list(weapons.keys()),
            show_choices=True
        )
        
        # Resume live display
        if self.live:
            self.live.start()
        
        return choice

    def get_price_range(self) -> tuple:
        """Get price range for analysis."""
        min_price = IntPrompt.ask(
            "Enter minimum price (in USD)",
            default=str(self.config['analysis']['min_price'])
        )
        max_price = IntPrompt.ask(
            "Enter maximum price (in USD)",
            default=str(self.config['analysis']['max_price'])
        )
        return min_price, max_price

    def create_progress_bar(self) -> Progress:
        """Create an enhanced progress bar for scraping operations."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=True
        )

    def display_results(self, items: List[Dict[str, Any]]):
        """Display scraped items in a formatted table with enhanced visuals."""
        if not items:
            self.show_warning("No items found!")
            return

        self.items_analyzed += len(items)
        
        table = Table(
            title="Market Items Analysis",
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
            title_style="bold cyan",
            caption=f"Total Items: {len(items)}"
        )
        
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Price", style="green", justify="right")
        table.add_column("Wear", style="blue")
        table.add_column("StatTrak", style="magenta", justify="center")
        table.add_column("Souvenir", style="yellow", justify="center")
        table.add_column("Profit Potential", style="red", justify="right")

        # Sort items by price for better visualization
        items.sort(key=lambda x: float(x["price"].replace("$", "").replace(",", "")))

        for item in items:
            price = float(item["price"].replace("$", "").replace(",", ""))
            profit_potential = self._calculate_profit_potential(price)
            
            table.add_row(
                item["name"],
                item["price"],
                item.get("wear", "N/A"),
                "✓" if item["stat"] else "✗",
                "✓" if item["souv"] else "✗",
                f"{profit_potential:+.2f}%" if profit_potential else "N/A"
            )

        # Update using existing live context
        self.layout["content"].update(Panel(table))
        self.layout["sidebar"].update(self._create_stats_panel())
        
        # Temporarily suspend live display for input
        if self.live:
            self.live.stop()
        self.console.input("\nPress Enter to continue...")
        if self.live:
            self.live.start()

    def display_trade_up_opportunities(self, opportunities: List[TradeUpContract]):
        """Display trade-up contract opportunities."""
        if not opportunities:
            self.show_warning("No profitable trade-up opportunities found!")
            return

        table = Table(
            title="Trade-Up Contract Opportunities",
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
            title_style="bold cyan",
            caption=f"Total Opportunities: {len(opportunities)}"
        )
        
        table.add_column("Input Items", style="cyan")
        table.add_column("Potential Outputs", style="green")
        table.add_column("Cost", style="yellow", justify="right")
        table.add_column("Expected Value", style="blue", justify="right")
        table.add_column("Profit", style="red", justify="right")
        table.add_column("Risk", style="magenta", justify="center")
        table.add_column("Success", style="green", justify="right")

        for contract in opportunities:
            input_names = ", ".join(item["name"].split("|")[1].strip() for item in contract.input_items[:3])
            if len(contract.input_items) > 3:
                input_names += f" +{len(contract.input_items)-3} more"

            output_names = ", ".join(item["name"].split("|")[1].strip() for item in contract.potential_outputs[:2])
            if len(contract.potential_outputs) > 2:
                output_names += f" +{len(contract.potential_outputs)-2} more"

            table.add_row(
                input_names,
                output_names,
                f"${contract.cost:.2f}",
                f"${contract.expected_value:.2f}",
                f"{contract.profit_margin:+.1f}%",
                contract.risk_level,
                f"{contract.success_chance*100:.0f}%"
            )

        # Update using existing live context
        self.layout["content"].update(Panel(table))
        
        # Temporarily suspend live display for input
        if self.live:
            self.live.stop()
        self.console.input("\nPress Enter to continue...")
        if self.live:
            self.live.start()

    def show_detailed_contract(self, contract: TradeUpContract):
        """Show detailed information about a trade-up contract."""
        # Input items table
        input_table = Table(title="Input Items", show_header=True)
        input_table.add_column("Name", style="cyan")
        input_table.add_column("Wear", style="blue")
        input_table.add_column("Price", style="green", justify="right")
        
        for item in contract.input_items:
            input_table.add_row(
                item["name"],
                item["wear"],
                item["price"]
            )

        # Output items table
        output_table = Table(title="Potential Outputs", show_header=True)
        output_table.add_column("Name", style="cyan")
        output_table.add_column("Wear", style="blue")
        output_table.add_column("Price", style="green", justify="right")
        
        for item in contract.potential_outputs:
            output_table.add_row(
                item["name"],
                item["wear"],
                item["price"]
            )

        # Summary table
        summary_table = Table(show_header=False)
        summary_table.add_row("Total Cost", f"${contract.cost:.2f}")
        summary_table.add_row("Expected Value", f"${contract.expected_value:.2f}")
        summary_table.add_row("Profit Margin", f"{contract.profit_margin:+.1f}%")
        summary_table.add_row("Risk Level", contract.risk_level)
        summary_table.add_row("Success Chance", f"{contract.success_chance*100:.0f}%")
        summary_table.add_row("Float Range", f"{contract.float_range[0]:.3f} - {contract.float_range[1]:.3f}")

        # Update using existing live context
        self.layout["content"].update(
            Panel(
                Columns([input_table, output_table]),
                title="Trade-Up Contract Details"
            )
        )
        self.layout["sidebar"].update(Panel(summary_table, title="Summary"))
        
        # Temporarily suspend live display for input
        if self.live:
            self.live.stop()
        self.console.input("\nPress Enter to continue...")
        if self.live:
            self.live.start()

    def _calculate_profit_potential(self, price: float) -> float:
        """Calculate potential profit percentage based on market analysis."""
        if price < self.config['analysis']['min_price']:
            return 0
        if price > self.config['analysis']['max_price']:
            return 0
        return ((self.config['analysis']['max_price'] - price) / price) * 100

    def show_market_analysis(self, items: List[Dict[str, Any]]):
        """Show detailed market analysis."""
        if not items:
            return

        prices = [float(item["price"].replace("$", "").replace(",", "")) for item in items]
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)

        # Create wear distribution
        wear_dist = {}
        for item in items:
            wear = item.get("wear", "Unknown")
            wear_dist[wear] = wear_dist.get(wear, 0) + 1

        # Create price distribution
        price_ranges = {
            "< $1": 0,
            "$1 - $5": 0,
            "$5 - $10": 0,
            "$10 - $50": 0,
            "$50 - $100": 0,
            "> $100": 0
        }
        
        for price in prices:
            if price < 1:
                price_ranges["< $1"] += 1
            elif price < 5:
                price_ranges["$1 - $5"] += 1
            elif price < 10:
                price_ranges["$5 - $10"] += 1
            elif price < 50:
                price_ranges["$10 - $50"] += 1
            elif price < 100:
                price_ranges["$50 - $100"] += 1
            else:
                price_ranges["> $100"] += 1

        # Create analysis tables
        price_table = Table(title="Price Analysis", show_header=False)
        price_table.add_row("Average Price", f"${avg_price:.2f}")
        price_table.add_row("Minimum Price", f"${min_price:.2f}")
        price_table.add_row("Maximum Price", f"${max_price:.2f}")
        price_table.add_row("Total Items", str(len(items)))

        dist_table = Table(title="Price Distribution")
        dist_table.add_column("Range", style="cyan")
        dist_table.add_column("Count", style="green", justify="right")
        dist_table.add_column("Percentage", style="blue", justify="right")
        
        for price_range, count in price_ranges.items():
            percentage = (count / len(items)) * 100
            dist_table.add_row(
                price_range,
                str(count),
                f"{percentage:.1f}%"
            )

        wear_table = Table(title="Wear Distribution")
        wear_table.add_column("Condition", style="cyan")
        wear_table.add_column("Count", style="green", justify="right")
        wear_table.add_column("Percentage", style="blue", justify="right")
        
        for wear, count in wear_dist.items():
            percentage = (count / len(items)) * 100
            wear_table.add_row(
                wear,
                str(count),
                f"{percentage:.1f}%"
            )

        # Update using existing live context
        self.layout["content"].update(
            Panel(
                Columns([price_table, dist_table]),
                title="Market Analysis"
            )
        )
        self.layout["sidebar"].update(Panel(wear_table, title="Wear Analysis"))
        
        # Temporarily suspend live display for input
        if self.live:
            self.live.stop()
        self.console.input("\nPress Enter to continue...")
        if self.live:
            self.live.start()

    def confirm_action(self, message: str) -> bool:
        """Get user confirmation for an action with enhanced visuals."""
        return Confirm.ask(f"[cyan]{message}[/cyan]")

    def show_error(self, message: str):
        """Display error message with enhanced visuals."""
        panel = Panel(
            f"[red]{message}[/red]",
            title="Error",
            border_style="red"
        )
        self.console.print(panel)

    def show_success(self, message: str):
        """Display success message with enhanced visuals."""
        panel = Panel(
            f"[green]{message}[/green]",
            title="Success",
            border_style="green"
        )
        self.console.print(panel)

    def show_warning(self, message: str):
        """Display warning message with enhanced visuals."""
        panel = Panel(
            f"[yellow]{message}[/yellow]",
            title="Warning",
            border_style="yellow"
        )
        self.console.print(panel)

    def show_help(self):
        """Display help information."""
        help_text = """
        # TradeUpTrends Help

        ## Features
        - Real-time market data analysis
        - Trade-up contract calculator
        - Profit potential analysis
        - Risk assessment
        - Market trends and statistics

        ## Commands
        - Select weapon by name or index
        - Set price range for analysis
        - View market statistics
        - Analyze trade-up opportunities
        - View detailed contract information

        ## Tips
        - Use arrow keys to navigate
        - Press Ctrl+C to exit
        - Prices are in USD
        - Green indicators show profitable opportunities
        - Risk levels: Low, Medium, High
        """
        
        markdown = Markdown(help_text)
        self.layout["content"].update(Panel(markdown, title="Help", border_style="blue"))
        
        # Temporarily suspend live display for input
        if self.live:
            self.live.stop()
        self.console.input("\nPress Enter to continue...")
        if self.live:
            self.live.start()

    def _analyze_market(self):
        """Handle market analysis workflow."""
        try:
            if not self.scraper:
                from scraper import Scraper
                from temp import items_dict
                self.scraper = Scraper(self.config['scraping']['base_url'], items_dict)

            # Get weapon selection
            weapon = self.get_weapon_selection(self.scraper.items_dict)
            if not weapon:
                return

            # Get price range
            min_price, max_price = self.get_price_range()

            # Create progress bar for scraping
            with self.create_progress_bar() as progress:
                task = progress.add_task(
                    f"[cyan]Scraping {weapon.upper()} market data...",
                    total=None
                )
                
                # Scrape items
                items = self.scraper.get_items(weapon)
                progress.update(task, completed=True)

            # Display results and analysis
            self.display_results(items)
            self.show_market_analysis(items)

            # Ask if user wants to continue
            if not self.confirm_action("Would you like to analyze another weapon?"):
                self.current_menu = "main"
                self.selected_index = 0

        except Exception as e:
            logger.exception(f"Error in market analysis")
            self.show_error(f"Error analyzing market: {str(e)}")
            time.sleep(2)  # Give user time to read error
            self.current_menu = "main"
            self.selected_index = 0

    def _find_trade_up_contracts(self):
        """Handle trade-up contract analysis workflow."""
        try:
            if not self.scraper:
                from scraper import Scraper
                from temp import items_dict
                self.scraper = Scraper(self.config['scraping']['base_url'], items_dict)

            if not self.calculator:
                from trade_up_calculator import TradeUpCalculator
                self.calculator = TradeUpCalculator(self.config)

            # Get weapon selection
            weapon = self.get_weapon_selection(self.scraper.items_dict)
            if not weapon:
                return

            # Create progress bar for scraping
            with self.create_progress_bar() as progress:
                task = progress.add_task(
                    f"[cyan]Scraping {weapon.upper()} market data...",
                    total=None
                )
                
                # Scrape items
                items = self.scraper.get_items(weapon)
                progress.update(task, completed=True)

            # Find trade-up opportunities
            with self.create_progress_bar() as progress:
                task = progress.add_task(
                    "[cyan]Analyzing trade-up opportunities...",
                    total=None
                )
                opportunities = self.calculator.find_trade_up_opportunities(items)
                progress.update(task, completed=True)

            # Display opportunities
            self.display_trade_up_opportunities(opportunities)

            # Show detailed analysis for best opportunities
            for contract in opportunities[:3]:  # Show top 3 opportunities
                if self.confirm_action("Would you like to see detailed analysis for this trade-up contract?"):
                    self.show_detailed_contract(contract)
                else:
                    break

            # Ask if user wants to continue
            if not self.confirm_action("Would you like to analyze another weapon?"):
                self.current_menu = "main"
                self.selected_index = 0

        except Exception as e:
            logger.exception(f"Error in trade-up analysis")
            self.show_error(f"Error analyzing trade-up contracts: {str(e)}")
            time.sleep(2)  # Give user time to read error
            self.current_menu = "main"
            self.selected_index = 0 