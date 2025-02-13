from rich.console import Console, Group
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
from rich.rule import Rule
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from trade_up_calculator import TradeUpContract
import time
import keyboard

class ConsoleUI:
    def __init__(self, config=None):
        self.console = Console()
        if config is None:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
        else:
            self.config = config
            
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
        self.shutting_down = False
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Log startup configuration
        if self.config.get('scraping', {}).get('use_vpn') is False:
            self.logger.info("Running without VPN")
        if self.config.get('scraping', {}).get('use_proxy') is False:
            self.logger.info("Running without proxies")
        if self.config.get('logging', {}).get('level') == 'DEBUG':
            self.logger.info("Debug logging enabled")
        
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
        try:
            # Set up static UI elements once
            title = Text("TradeUpTrends", style=f"bold {self.config['ui']['color_scheme']['primary']}")
            subtitle = Text("CS2 Market Analysis Tool", style=f"italic {self.config['ui']['color_scheme']['secondary']}")
            
            header_content = Panel(
                title + "\n" + subtitle,
                border_style=self.config['ui']['color_scheme']['primary'],
                padding=(1, 2),
                title="Welcome"
            )
            
            # Set up initial layout
            self.layout["header"].update(header_content)
            self.layout["footer"].update(self._create_footer())
            self.layout["sidebar"].update(self._create_stats_panel())
            self.layout["content"].update(self._create_menu_panel())
            
            # Clear screen once before starting Live display
            self.console.clear()
            
            # Initialize Live display with proper configuration
            with Live(
                self.layout,
                console=self.console,
                screen=True,
                refresh_per_second=self.config['ui']['refresh_rate']
            ) as live:
                self.live = live
                
                # Initial refresh to show the UI
                live.refresh()
                
                while self.running:
                    try:
                        current_time = time.time()
                        
                        # Handle keyboard input
                        if keyboard.is_pressed('ctrl+r') and current_time - self.last_key_time >= self.key_cooldown:
                            self.last_key_time = current_time
                            # Force refresh all UI elements
                            self._refresh_all_panels()
                            continue
                            
                        if keyboard.is_pressed('up') and current_time - self.last_key_time >= self.key_cooldown:
                            self.selected_index = max(0, self.selected_index - 1)
                            self.last_key_time = current_time
                            self._refresh_menu()
                            
                        elif keyboard.is_pressed('down') and current_time - self.last_key_time >= self.key_cooldown:
                            menu_items = self.config['ui']['display']['menu'][self.current_menu]
                            self.selected_index = min(len(menu_items) - 1, self.selected_index + 1)
                            self.last_key_time = current_time
                            self._refresh_menu()
                            
                        elif keyboard.is_pressed('enter') and current_time - self.last_key_time >= self.key_cooldown:
                            self.last_key_time = current_time
                            menu_items = self.config['ui']['display']['menu'][self.current_menu]
                            selected_item = menu_items[self.selected_index]
                            
                            if selected_item in ["Analyze Market", "Find Trade-Up Contracts"]:
                                # Show processing message
                                self._show_processing_panel(f"Starting {selected_item.lower()}...")
                                
                                # Handle long operation
                                if selected_item == "Analyze Market":
                                    self._analyze_market()
                                else:
                                    self._find_trade_up_contracts()
                                    
                                # Restore menu after operation
                                self.current_menu = "main"
                                self.selected_index = 0
                                self._refresh_all_panels()
                            else:
                                self._handle_menu_selection()
                                self._refresh_all_panels()
                            
                        elif keyboard.is_pressed('esc') and current_time - self.last_key_time >= self.key_cooldown:
                            self.last_key_time = current_time
                            
                            if self.current_menu == "main":
                                if self.confirm_action("Are you sure you want to exit?"):
                                    self.shutdown()
                                    break
                            else:
                                self.current_menu = "main"
                                self.selected_index = 0
                                self._refresh_menu()
                        
                        time.sleep(0.05)
                        
                    except KeyboardInterrupt:
                        if self.confirm_action("Are you sure you want to exit?"):
                            self.shutdown()
                            break
                        
        except Exception as e:
            self.logger.exception("An error occurred in the main UI loop")
            self.show_error(f"An error occurred: {str(e)}")
        finally:
            if not self.shutting_down:
                self.shutdown()

    def _refresh_menu(self):
        """Refresh just the menu panel."""
        if self.live and self.live.is_started:
            self.layout["content"].update(self._create_menu_panel())
            self.live.refresh()

    def _refresh_all_panels(self):
        """Refresh all panels in the layout."""
        if self.live and self.live.is_started:
            self.layout["header"].update(self._create_header())
            self.layout["footer"].update(self._create_footer())
            self.layout["sidebar"].update(self._create_stats_panel())
            self.layout["content"].update(self._create_menu_panel())
            self.live.refresh()

    def _show_processing_panel(self, message: str):
        """Show a processing message panel."""
        if self.live and self.live.is_started:
            self.layout["content"].update(Panel(
                Text(message, style="cyan"),
                title="Processing",
                border_style="blue"
            ))
            self.live.refresh()

    def _handle_input(self):
        """Handle keyboard input."""
        current_time = time.time()
        
        if current_time - self.last_key_time < self.key_cooldown:
            return
            
        needs_update = False
        if keyboard.is_pressed('up'):
            self.selected_index = max(0, self.selected_index - 1)
            self.last_key_time = current_time
            needs_update = True
        elif keyboard.is_pressed('down'):
            menu_items = self.config['ui']['display']['menu'][self.current_menu]
            self.selected_index = min(len(menu_items) - 1, self.selected_index + 1)
            self.last_key_time = current_time
            needs_update = True
        elif keyboard.is_pressed('enter'):
            self._handle_menu_selection()
            self.last_key_time = current_time
            needs_update = True
        elif keyboard.is_pressed('esc'):
            if self.current_menu == "main":
                self.running = False
            else:
                self.current_menu = "main"
                self.selected_index = 0
            self.last_key_time = current_time
            needs_update = True
            
        if needs_update:
            self.layout["content"].update(self._create_menu_panel())

    def _handle_menu_selection(self):
        """Handle menu item selection."""
        menu_items = self.config['ui']['display']['menu'][self.current_menu]
        selected_item = menu_items[self.selected_index]
        
        if self.current_menu == "main":
            if selected_item == "Exit":
                self.shutdown()
            elif selected_item == "Settings":
                self.current_menu = "settings"
                self.selected_index = 0
                # Update both content and sidebar to ensure UI stays responsive
                self.layout["content"].update(self._create_menu_panel())
                self.layout["sidebar"].update(self._create_stats_panel())
                if self.live and self.live.is_started:
                    self.live.refresh()
            elif selected_item == "Analyze Market":
                # Create a temporary panel to show we're starting analysis
                processing_panel = Panel(
                    Text("Starting market analysis...", style="cyan"),
                    title="Market Analysis",
                    border_style="blue"
                )
                self.layout["content"].update(processing_panel)
                if self.live and self.live.is_started:
                    self.live.refresh()
                
                # Temporarily stop live display
                if self.live and self.live.is_started:
                    self.live.stop()
                try:
                    self._analyze_market()
                finally:
                    # Ensure we restart the live display and restore the menu
                    if self.live:
                        self.current_menu = "main"
                        self.selected_index = 0
                        self.layout["content"].update(self._create_menu_panel())
                        self.layout["sidebar"].update(self._create_stats_panel())
                        self.live.start()
                        self.live.refresh()
                        
            elif selected_item == "Find Trade-Up Contracts":
                # Create a temporary panel to show we're starting analysis
                processing_panel = Panel(
                    Text("Starting trade-up contract analysis...", style="cyan"),
                    title="Trade-Up Analysis",
                    border_style="blue"
                )
                self.layout["content"].update(processing_panel)
                if self.live and self.live.is_started:
                    self.live.refresh()
                
                # Temporarily stop live display
                if self.live and self.live.is_started:
                    self.live.stop()
                try:
                    self._find_trade_up_contracts()
                finally:
                    # Ensure we restart the live display and restore the menu
                    if self.live:
                        self.current_menu = "main"
                        self.selected_index = 0
                        self.layout["content"].update(self._create_menu_panel())
                        self.layout["sidebar"].update(self._create_stats_panel())
                        self.live.start()
                        self.live.refresh()
                        
            elif selected_item == "Help":
                self.show_help()
        elif self.current_menu == "settings":
            self._handle_settings_menu()
        elif self.current_menu == "scraping_settings":
            self._handle_scraping_settings()
        elif self.current_menu == "analysis_settings":
            self._handle_analysis_settings()
        elif self.current_menu == "vpn_settings":
            self._handle_vpn_settings()
        elif self.current_menu == "proxy_settings":
            self._handle_proxy_settings()
        elif self.current_menu == "ui_settings":
            self._handle_ui_settings()

        # Always ensure the UI is refreshed after any menu action
        if self.live and self.live.is_started:
            self.live.refresh()

    def _handle_settings_menu(self):
        """Handle settings menu selection."""
        menu_items = self.config['ui']['display']['menu']['settings']
        selected_item = menu_items[self.selected_index]
        
        if selected_item == "Back to Main Menu":
            self.current_menu = "main"
            self.selected_index = 0
        elif selected_item == "Scraping Settings":
            self._handle_scraping_settings()
        elif selected_item == "Analysis Settings":
            self._handle_analysis_settings()
        elif selected_item == "VPN Settings":
            self._handle_vpn_settings()
        elif selected_item == "Proxy Settings":
            self._handle_proxy_settings()
        elif selected_item == "UI Settings":
            self._handle_ui_settings()

    def _handle_scraping_settings(self):
        """Handle scraping settings menu."""
        settings_table = Table(show_header=False, box=None)
        settings_table.add_row(
            "Minimum Delay:",
            f"[cyan]{self.config['scraping']['min_delay']}[/cyan] seconds"
        )
        settings_table.add_row(
            "Maximum Delay:",
            f"[cyan]{self.config['scraping']['max_delay']}[/cyan] seconds"
        )
        settings_table.add_row(
            "Save Progress:",
            f"[cyan]{str(self.config['scraping']['save_progress'])}[/cyan]"
        )
        settings_table.add_row(
            "Request Timeout:",
            f"[cyan]{self.config['scraping']['request_timeout']}[/cyan] seconds"
        )
        
        self.layout["content"].update(Panel(
            Group(
                settings_table,
                Text("\nPress Enter to modify, Esc to go back", style="cyan")
            ),
            title="Scraping Settings",
            border_style="blue"
        ))
        if self.live:
            self.live.refresh()
            
        # Wait for user input
        while True:
            if keyboard.is_pressed('enter'):
                self._modify_scraping_settings()
                break
            elif keyboard.is_pressed('esc'):
                break
            time.sleep(0.05)
            
        self.current_menu = "settings"
        self.selected_index = 0

    def _modify_scraping_settings(self):
        """Modify scraping settings."""
        if self.live:
            self.live.stop()
        
        try:
            min_delay = float(Prompt.ask("Enter minimum delay (seconds)", default=str(self.config['scraping']['min_delay'])))
            max_delay = float(Prompt.ask("Enter maximum delay (seconds)", default=str(self.config['scraping']['max_delay'])))
            save_progress = Confirm.ask("Save progress?", default=self.config['scraping']['save_progress'])
            timeout = int(Prompt.ask("Enter request timeout (seconds)", default=str(self.config['scraping']['request_timeout'])))
            
            # Update config
            self.config['scraping']['min_delay'] = min_delay
            self.config['scraping']['max_delay'] = max_delay
            self.config['scraping']['save_progress'] = save_progress
            self.config['scraping']['request_timeout'] = timeout
            
            # Save to file
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
                
            self.show_success("Settings updated successfully!")
            
        except Exception as e:
            self.show_error(f"Error updating settings: {str(e)}")
        finally:
            if self.live:
                self.live.start()

    def _handle_analysis_settings(self):
        """Handle analysis settings menu."""
        settings_table = Table(show_header=False, box=None)
        settings_table.add_row(
            "Minimum Price:",
            f"[cyan]${self.config['analysis']['min_price']}[/cyan]"
        )
        settings_table.add_row(
            "Maximum Price:",
            f"[cyan]${self.config['analysis']['max_price']}[/cyan]"
        )
        settings_table.add_row(
            "Minimum Volume:",
            f"[cyan]{self.config['analysis']['min_volume']}[/cyan]"
        )
        settings_table.add_row(
            "Minimum Profit Margin:",
            f"[cyan]{self.config['analysis']['min_profit_margin']}%[/cyan]"
        )
        
        self.layout["content"].update(Panel(
            Group(
                settings_table,
                Text("\nPress Enter to modify, Esc to go back", style="cyan")
            ),
            title="Analysis Settings",
            border_style="blue"
        ))
        if self.live:
            self.live.refresh()
            
        # Wait for user input
        while True:
            if keyboard.is_pressed('enter'):
                self._modify_analysis_settings()
                break
            elif keyboard.is_pressed('esc'):
                break
            time.sleep(0.05)
            
        self.current_menu = "settings"
        self.selected_index = 1

    def _modify_analysis_settings(self):
        """Modify analysis settings."""
        if self.live:
            self.live.stop()
        
        try:
            min_price = float(Prompt.ask("Enter minimum price ($)", default=str(self.config['analysis']['min_price'])))
            max_price = float(Prompt.ask("Enter maximum price ($)", default=str(self.config['analysis']['max_price'])))
            min_volume = int(Prompt.ask("Enter minimum volume", default=str(self.config['analysis']['min_volume'])))
            min_profit = float(Prompt.ask("Enter minimum profit margin (%)", default=str(self.config['analysis']['min_profit_margin'])))
            
            # Update config
            self.config['analysis']['min_price'] = min_price
            self.config['analysis']['max_price'] = max_price
            self.config['analysis']['min_volume'] = min_volume
            self.config['analysis']['min_profit_margin'] = min_profit
            
            # Save to file
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
                
            self.show_success("Settings updated successfully!")
            
        except Exception as e:
            self.show_error(f"Error updating settings: {str(e)}")
        finally:
            if self.live:
                self.live.start()

    def _handle_vpn_settings(self):
        """Handle VPN settings menu."""
        settings_table = Table(show_header=False, box=None)
        vpn_settings = self.config['scraping']['vpn_settings']
        settings_table.add_row(
            "Use VPN:",
            f"[cyan]{str(self.config['scraping']['use_vpn'])}[/cyan]"
        )
        settings_table.add_row(
            "Auto Rotate:",
            f"[cyan]{str(vpn_settings['auto_rotate'])}[/cyan]"
        )
        settings_table.add_row(
            "Rotate Interval:",
            f"[cyan]{vpn_settings['rotate_interval']}[/cyan] seconds"
        )
        settings_table.add_row(
            "Preferred Locations:",
            f"[cyan]{', '.join(vpn_settings['preferred_locations'])}[/cyan]"
        )
        
        self.layout["content"].update(Panel(
            Group(
                settings_table,
                Text("\nPress Enter to modify, Esc to go back", style="cyan")
            ),
            title="VPN Settings",
            border_style="blue"
        ))
        if self.live:
            self.live.refresh()
            
        # Wait for user input
        while True:
            if keyboard.is_pressed('enter'):
                self._modify_vpn_settings()
                break
            elif keyboard.is_pressed('esc'):
                break
            time.sleep(0.05)
            
        self.current_menu = "settings"
        self.selected_index = 2

    def _modify_vpn_settings(self):
        """Modify VPN settings."""
        if self.live:
            self.live.stop()
        
        try:
            use_vpn = Confirm.ask("Use VPN?", default=self.config['scraping']['use_vpn'])
            auto_rotate = Confirm.ask("Auto rotate VPN?", default=self.config['scraping']['vpn_settings']['auto_rotate'])
            rotate_interval = int(Prompt.ask(
                "Enter rotation interval (seconds)",
                default=str(self.config['scraping']['vpn_settings']['rotate_interval'])
            ))
            locations = Prompt.ask(
                "Enter preferred locations (comma-separated)",
                default=",".join(self.config['scraping']['vpn_settings']['preferred_locations'])
            ).split(',')
            
            # Update config
            self.config['scraping']['use_vpn'] = use_vpn
            self.config['scraping']['vpn_settings']['auto_rotate'] = auto_rotate
            self.config['scraping']['vpn_settings']['rotate_interval'] = rotate_interval
            self.config['scraping']['vpn_settings']['preferred_locations'] = [loc.strip() for loc in locations]
            
            # Save to file
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
                
            self.show_success("VPN settings updated successfully!")
            
        except Exception as e:
            self.show_error(f"Error updating VPN settings: {str(e)}")
        finally:
            if self.live:
                self.live.start()

    def _handle_proxy_settings(self):
        """Handle proxy settings menu."""
        settings_table = Table(show_header=False, box=None)
        settings_table.add_row(
            "Use Proxies:",
            f"[cyan]{str(self.config['scraping']['use_proxy'])}[/cyan]"
        )
        settings_table.add_row(
            "Minimum Working Proxies:",
            f"[cyan]{self.config['scraping']['min_working_proxies']}[/cyan]"
        )
        settings_table.add_row(
            "Check Interval:",
            f"[cyan]{self.config['scraping']['proxy_check_interval']}[/cyan] seconds"
        )
        settings_table.add_row(
            "Test Timeout:",
            f"[cyan]{self.config['scraping']['proxy_test_timeout']}[/cyan] seconds"
        )
        
        self.layout["content"].update(Panel(
            Group(
                settings_table,
                Text("\nPress Enter to modify, Esc to go back", style="cyan")
            ),
            title="Proxy Settings",
            border_style="blue"
        ))
        if self.live:
            self.live.refresh()
            
        # Wait for user input
        while True:
            if keyboard.is_pressed('enter'):
                self._modify_proxy_settings()
                break
            elif keyboard.is_pressed('esc'):
                break
            time.sleep(0.05)
            
        self.current_menu = "settings"
        self.selected_index = 3

    def _modify_proxy_settings(self):
        """Modify proxy settings."""
        if self.live:
            self.live.stop()
        
        try:
            use_proxy = Confirm.ask("Use proxies?", default=self.config['scraping']['use_proxy'])
            min_proxies = int(Prompt.ask(
                "Enter minimum working proxies",
                default=str(self.config['scraping']['min_working_proxies'])
            ))
            check_interval = int(Prompt.ask(
                "Enter check interval (seconds)",
                default=str(self.config['scraping']['proxy_check_interval'])
            ))
            test_timeout = int(Prompt.ask(
                "Enter test timeout (seconds)",
                default=str(self.config['scraping']['proxy_test_timeout'])
            ))
            
            # Update config
            self.config['scraping']['use_proxy'] = use_proxy
            self.config['scraping']['min_working_proxies'] = min_proxies
            self.config['scraping']['proxy_check_interval'] = check_interval
            self.config['scraping']['proxy_test_timeout'] = test_timeout
            
            # Save to file
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
                
            self.show_success("Proxy settings updated successfully!")
            
        except Exception as e:
            self.show_error(f"Error updating proxy settings: {str(e)}")
        finally:
            if self.live:
                self.live.start()

    def _handle_ui_settings(self):
        """Handle UI settings menu."""
        settings_table = Table(show_header=False, box=None)
        settings_table.add_row(
            "Refresh Rate:",
            f"[cyan]{self.config['ui']['refresh_rate']}[/cyan] Hz"
        )
        settings_table.add_row(
            "Show Animations:",
            f"[cyan]{str(self.config['ui']['show_loading_animations'])}[/cyan]"
        )
        settings_table.add_row(
            "Show Progress Bars:",
            f"[cyan]{str(self.config['ui']['show_progress_bars'])}[/cyan]"
        )
        settings_table.add_row(
            "Compact Mode:",
            f"[cyan]{str(self.config['ui']['compact_mode'])}[/cyan]"
        )
        
        self.layout["content"].update(Panel(
            Group(
                settings_table,
                Text("\nPress Enter to modify, Esc to go back", style="cyan")
            ),
            title="UI Settings",
            border_style="blue"
        ))
        if self.live:
            self.live.refresh()
            
        # Wait for user input
        while True:
            if keyboard.is_pressed('enter'):
                self._modify_ui_settings()
                break
            elif keyboard.is_pressed('esc'):
                break
            time.sleep(0.05)
            
        self.current_menu = "settings"
        self.selected_index = 4

    def _modify_ui_settings(self):
        """Modify UI settings."""
        if self.live:
            self.live.stop()
        
        try:
            refresh_rate = int(Prompt.ask("Enter refresh rate (Hz)", default=str(self.config['ui']['refresh_rate'])))
            show_animations = Confirm.ask("Show loading animations?", default=self.config['ui']['show_loading_animations'])
            show_progress = Confirm.ask("Show progress bars?", default=self.config['ui']['show_progress_bars'])
            compact_mode = Confirm.ask("Use compact mode?", default=self.config['ui']['compact_mode'])
            
            # Update config
            self.config['ui']['refresh_rate'] = refresh_rate
            self.config['ui']['show_loading_animations'] = show_animations
            self.config['ui']['show_progress_bars'] = show_progress
            self.config['ui']['compact_mode'] = compact_mode
            
            # Save to file
            with open('config.json', 'w') as f:
                json.dump(self.config, f, indent=4)
                
            self.show_success("UI settings updated successfully!")
            
        except Exception as e:
            self.show_error(f"Error updating UI settings: {str(e)}")
        finally:
            if self.live:
                self.live.start()

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
            
            # Just wait for enter to start
            self.console.print("\n[cyan]Press Enter to start...[/cyan]")
            keyboard.wait('enter')
            
            # Clear the initial prompt
            self.console.clear()
            self._update_display()
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
            "[blue]Esc[/blue]: Back/Exit",
            "[blue]Ctrl+R[/blue]: Refresh UI"
        ]
        return Panel(
            Text(" | ".join(controls), justify="center"),
            border_style=self.config['ui']['color_scheme']['primary']
        )

    def get_weapon_selection(self, weapons: Dict[str, str]) -> str:
        """Display weapon selection menu and get user choice."""
        weapons_list = list(weapons.keys())
        selected_index = 0
        
        # Create initial weapon selection UI
        table = self._create_weapon_table(weapons_list, selected_index)
        
        # Update the layout with the weapon selection table
        self.layout["content"].update(Panel(table, title="Weapon Selection"))
        self.layout["sidebar"].update(self._create_stats_panel())
        if self.live:
            self.live.refresh()
        
        # Handle weapon selection input
        current_time = time.time()
        last_key_time = current_time
        
        while True:
            try:
                current_time = time.time()
                needs_update = False
                
                if keyboard.is_pressed('up') and current_time - last_key_time >= self.key_cooldown:
                    selected_index = (selected_index - 1) % len(weapons_list)
                    last_key_time = current_time
                    needs_update = True
                    
                elif keyboard.is_pressed('down') and current_time - last_key_time >= self.key_cooldown:
                    selected_index = (selected_index + 1) % len(weapons_list)
                    last_key_time = current_time
                    needs_update = True
                    
                elif keyboard.is_pressed('enter') and current_time - last_key_time >= self.key_cooldown:
                    return weapons_list[selected_index]
                    
                elif keyboard.is_pressed('esc') and current_time - last_key_time >= self.key_cooldown:
                    return None
                
                if needs_update:
                    table = self._create_weapon_table(weapons_list, selected_index)
                    self.layout["content"].update(Panel(table, title="Weapon Selection"))
                    if self.live:
                        self.live.refresh()
                
                time.sleep(0.05)
            except Exception as e:
                self.logger.exception("Error in weapon selection")
                return None

    def _create_weapon_table(self, weapons_list: List[str], selected_index: int) -> Table:
        """Create the weapon selection table."""
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
        
        for i, weapon in enumerate(weapons_list):
            style = "bold cyan" if i == selected_index else "white"
            table.add_row(
                f"[{style}]{str(i+1)}[/{style}]",
                f"[{style}]{weapon.upper()}[/{style}]",
                f"[{style}]Loading...[/{style}]",
                f"[{style}]$ 0.03 - 1000.00[/{style}]"
            )
        
        return table

    def get_price_range(self) -> tuple:
        """Get price range for analysis."""
        # Create a form-like table for price input
        table = Table(show_header=False, box=None)
        table.add_row(
            "Enter minimum price (USD):",
            f"[cyan]{self.config['analysis']['min_price']}[/cyan]"
        )
        table.add_row(
            "Enter maximum price (USD):",
            f"[cyan]{self.config['analysis']['max_price']}[/cyan]"
        )
        
        self.layout["content"].update(Panel(table, title="Price Range Selection"))
        if self.live:
            self.live.refresh()
        
        # Use default values for now - we can implement interactive input later
        return (
            self.config['analysis']['min_price'],
            self.config['analysis']['max_price']
        )

    def create_progress_bar(self) -> Progress:
        """Create an enhanced progress bar for scraping operations."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            expand=True
        )
        
        # Create a group with the progress bar and stats
        progress_panel = Panel(
            Group(
                progress,
                Text("\nScraping Statistics:", style="bold cyan"),
                Text("Pages Processed: 0", style="green"),
                Text("Items Found: 0", style="yellow"),
                Text("Average Price: $0.00", style="blue"),
                Text("Time Elapsed: 0:00", style="magenta")
            ),
            title="Market Data Collection",
            border_style="blue"
        )
        
        # Update the sidebar with the progress panel
        self.layout["sidebar"].update(progress_panel)
        if self.live:
            self.live.refresh()
        
        return progress

    def update_scraping_stats(self, stats: Dict[str, Any]):
        """Update the scraping statistics in the sidebar."""
        stats_group = Group(
            Text("\nScraping Statistics:", style="bold cyan"),
            Text(f"Pages Processed: {stats['pages']}", style="green"),
            Text(f"Items Found: {stats['items']}", style="yellow"),
            Text(f"Average Price: ${stats['avg_price']:.2f}", style="blue"),
            Text(f"Time Elapsed: {stats['elapsed_time']}", style="magenta"),
            Rule(style="cyan"),
            Text("\nLatest Items:", style="bold cyan"),
            *(Text(f"• {item['name']}: {item['price']}", style="white") 
              for item in stats['recent_items'][-3:])  # Show last 3 items
        )
        
        progress_panel = Panel(
            stats_group,
            title="Market Data Collection",
            border_style="blue"
        )
        
        self.layout["sidebar"].update(progress_panel)
        if self.live:
            self.live.refresh()

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
        if self.live:
            self.live.refresh()
            
        # Wait for user input while keeping the display
        while True:
            if keyboard.is_pressed('enter'):
                break
            time.sleep(0.05)

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
        if self.live:
            self.live.refresh()
        
        # Wait for user input while keeping the display
        while True:
            if keyboard.is_pressed('enter'):
                break
            time.sleep(0.05)

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
        if self.live:
            self.live.refresh()
        
        # Wait for user input while keeping the display
        while True:
            if keyboard.is_pressed('enter'):
                break
            time.sleep(0.05)

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
        self.layout["content"].update(panel)
        if self.live:
            self.live.refresh()
        time.sleep(2)  # Give user time to read error

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

    def _find_trade_up_contracts(self):
        """Handle trade-up contract analysis workflow."""
        if self.live and self.live.is_started:
            self.live.stop()
            
        try:
            if not self.scraper:
                from scraper import Scraper
                from temp import items_dict
                self.scraper = Scraper(self.config['scraping']['base_url'], items_dict)

            if not self.calculator:
                from trade_up_calculator import TradeUpCalculator
                self.calculator = TradeUpCalculator(self.config)

            # Get weapon selection
            if self.live:
                self.live.start()
            weapon = self.get_weapon_selection(self.scraper.items_dict)
            if not weapon:
                return

            # Initialize scraping stats
            stats = {
                'pages': 0,
                'items': 0,
                'avg_price': 0.0,
                'elapsed_time': '0:00',
                'recent_items': []
            }
            start_time = time.time()

            # Show initial progress message
            self._show_processing_panel(f"Scraping {weapon.upper()} market data...")
            
            # Stop live display for the scraping operation
            if self.live and self.live.is_started:
                self.live.stop()

            # Scrape items
            items = []
            for item in self.scraper.get_items(weapon):
                items.append(item)
                
                # Update stats
                stats['items'] = len(items)
                stats['pages'] = (len(items) - 1) // 10 + 1
                prices = [float(i['price'].replace('$', '').replace(',', '').replace(' USD', '')) for i in items]
                stats['avg_price'] = sum(prices) / len(prices)
                stats['elapsed_time'] = str(datetime.timedelta(seconds=int(time.time() - start_time)))
                stats['recent_items'] = items[-3:] if len(items) > 3 else items

            # Show analysis progress message
            if self.live:
                self.live.start()
            self._show_processing_panel("Analyzing trade-up opportunities...")
            if self.live and self.live.is_started:
                self.live.stop()

            # Find trade-up opportunities
            opportunities = self.calculator.find_trade_up_opportunities(items)

            # Restart live display for showing results
            if self.live:
                self.live.start()

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
            self.logger.exception(f"Error in trade-up analysis")
            self.show_error(f"Error analyzing trade-up contracts: {str(e)}")
            time.sleep(2)  # Give user time to read error
        finally:
            self.current_menu = "main"
            self.selected_index = 0
            # Ensure live display is restarted
            if self.live and not self.live.is_started:
                self.live.start()
            self._refresh_all_panels()

    def _analyze_market(self):
        """Handle market analysis workflow."""
        try:
            if not self.scraper:
                from scraper import Scraper
                from temp import items_dict
                
                def update_progress(progress_info):
                    # Update the sidebar with progress information
                    progress_panel = Panel(
                        Group(
                            Text(f"\n{progress_info['status']}", style="bold cyan"),
                            Text(f"Pages: {progress_info['current_page']}/{progress_info['total_pages']}", style="green"),
                            Text(f"Items Found: {progress_info['items_found']}", style="yellow"),
                            Text(f"Time Elapsed: {progress_info['elapsed_time']}", style="blue"),
                            Rule(style="cyan"),
                            Text("\nRecent Items:", style="bold cyan"),
                            *(Text(f"• {item['name']}: {item['price']}", style="white") 
                              for item in progress_info['recent_items'][-3:])
                        ),
                        title="Market Analysis Progress",
                        border_style="blue"
                    )
                    self.layout["sidebar"].update(progress_panel)
                    if self.live and self.live.is_started:
                        self.live.refresh()
                
                self.scraper = Scraper(self.config['scraping']['base_url'], items_dict, progress_callback=update_progress)

            # Get weapon selection
            weapon = self.get_weapon_selection(self.scraper.items_dict)
            if not weapon:
                return

            # Create progress display
            progress_panel = Panel(
                Text("Starting market analysis...", style="cyan"),
                title="Market Analysis Progress",
                border_style="blue"
            )
            self.layout["sidebar"].update(progress_panel)
            if self.live and self.live.is_started:
                self.live.refresh()

            # Scrape items
            items = self.scraper.get_items(weapon)
            
            if items:
                # Show market analysis
                self.show_market_analysis(items)
                
                # Ask if user wants to continue
                if not self.confirm_action("Would you like to analyze another weapon?"):
                    self.current_menu = "main"
                    self.selected_index = 0

        except KeyboardInterrupt:
            self.logger.info("Market analysis interrupted by user")
            raise  # Re-raise to let the main loop handle it
        except Exception as e:
            self.logger.exception("Error in market analysis")
            self.show_error(f"Error analyzing market: {str(e)}")
            time.sleep(2)  # Give user time to read error
        finally:
            self.current_menu = "main"
            self.selected_index = 0

    def shutdown(self):
        """Gracefully shutdown the application."""
        if self.shutting_down:
            return
            
        self.shutting_down = True
        
        # Show shutdown confirmation
        if not self.confirm_action("Are you sure you want to exit?"):
            self.shutting_down = False
            return
            
        # Update UI to show shutdown status
        shutdown_panel = Panel(
            Group(
                Text("\nShutting down gracefully...", style="yellow"),
                Text("• Saving application state", style="cyan"),
                Text("• Cleaning up resources", style="cyan"),
                Text("• Closing connections", style="cyan")
            ),
            title="Shutdown in Progress",
            border_style="yellow"
        )
        
        self.layout["content"].update(shutdown_panel)
        if self.live:
            self.live.refresh()
        
        # Clean up resources
        if self.scraper:
            try:
                self.scraper.close()  # Assuming scraper has a close method
            except:
                pass
                
        if self.calculator:
            try:
                self.calculator.close()  # Assuming calculator has a close method
            except:
                pass
        
        # Final goodbye message
        final_panel = Panel(
            Text("\nThank you for using TradeUpTrends!\n", style="green"),
            title="Goodbye",
            border_style="green"
        )
        
        self.layout["content"].update(final_panel)
        if self.live:
            self.live.refresh()
            time.sleep(1)  # Give time to see the message
            self.live.stop()
        
        self.running = False 