from app.database import initialize_database, save_result
from rich.console import Console
from rich.panel import Panel

console = Console()

def show_monitoring_dashboard():
    from rich.table import Table
    from rich.panel import Panel
    from app.database import get_recent_results

    results = get_recent_results(100)

    total = len(results)

    online = sum(
        1 for row in results
        if row["status"] == "ONLINE"
    )

    offline = sum(
        1 for row in results
        if row["status"] == "OFFLINE"
    )

    open_services = sum(
        1 for row in results
        if row["check_type"] == "SERVICE_ENUMERATION"
        and row["status"] == "OPEN"
    )

    console.print(
        Panel(
            f"[bold cyan]Total Records:[/bold cyan] {total}\n"
            f"[green]Online Records:[/green] {online}\n"
            f"[red]Offline Records:[/red] {offline}\n"
            f"[yellow]Open Services:[/yellow] {open_services}",
            title="NMS Monitoring Summary",
            border_style="blue",
        )
    )

    table = Table(title="Recent Monitoring Activity")

    table.add_column("IP Address")
    table.add_column("Check Type")
    table.add_column("Status")
    table.add_column("Details")
    table.add_column("Checked At")

    for row in results:
        table.add_row(
            row["device_ip"],
            row["check_type"],
            row["status"],
            row["details"] or "-",
            row["checked_at"],
        )

    console.print(table)
def dashboard():
    while True:
        console.print(
            Panel(
                "[bold cyan]NMS NETWORK DIAGNOSTIC DASHBOARD[/bold cyan]\n\n"
                "1. Discover Devices\n"
                "2. Check Reachability\n"
                "3. Map Topology\n"
                "4. Enumerate Services\n"
                "5. Poll SNMP\n"
                "6. Monitoring Dashboard\n"
                "0. Exit",
                title="Main Menu",
                border_style="blue",
            )
        )

        choice = input("Enter your choice: ")

        
        if choice == "1":
            import ipaddress
            import platform
            import subprocess
            import concurrent.futures

            if platform.system() != "Windows":
                console.print(
                    "[red]This discovery version is configured for Windows.[/red]"
                )
            else:
                network_input = input(
                    "Enter your authorized network (CIDR): "
                ).strip()

                try:
                    network = ipaddress.ip_network(
                        network_input, strict=False
                    )

                    if network.num_addresses > 256:
                        console.print(
                            "[red]For this first version, use a network "
                            "with no more than 256 addresses.[/red]"
                        )
                    else:
                        hosts = list(network.hosts())
                        discovered = []

                        
                        def check_host(ip):
                            result = subprocess.run(
                                ["ping", "-n", "1", "-w", "1000", str(ip)],
                                capture_output=True,
                                text=True,
                                timeout=3,
                            )
                            return str(ip) if result.returncode == 0 else None

                        console.print(
                            f"[cyan]Checking {network}...[/cyan]"
                        )

                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=32
                        ) as executor:

                            for result in executor.map(check_host, hosts):
                                if result:
                                    discovered.append(result)

                                    console.print(
                                        f"[green]Device responded: {result}[/green]"
                                    )

                                    save_result(
                                        result,
                                        "DISCOVERY",
                                        "ONLINE",
                                        "Device discovered",
                                    )

                        console.print(
                            f"\n[bold]Devices responding to ping: "
                            f"{len(discovered)}[/bold]"
                        )



                except ValueError:
                    console.print(
                        "[red]Invalid network. Example: 192.168.1.0/24[/red]"
                    )
                except subprocess.TimeoutExpired:
                    console.print("[red]A ping command timed out.[/red]")


        
        elif choice == "2":
            import subprocess
            import platform
            import re

            target = input(
                "Enter the device IP address to check: "
            ).strip()

            try:
                # Validate the IPv4 address
                import ipaddress
                ipaddress.IPv4Address(target)

                # Send one ping and measure the response
                command = (
                    ["ping", "-n", "1", "-w", "2000", target]
                    if platform.system() == "Windows"
                    else ["ping", "-c", "1", "-W", "2", target]
                )

                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    match = re.search(
                        r"time[=<]\s*([\d.]+)\s*ms",
                        result.stdout,
                        re.IGNORECASE,
                    )

                    latency = (
                        match.group(1) + " ms"
                        if match
                        else "Reply received; latency unavailable"
                    )

                    console.print(
                        f"[green]ONLINE[/green] | {target} | "
                        f"Latency: {latency}"
                    )
                    save_result(
                        target,
                        "REACHABILITY",
                        "ONLINE",
                        latency,
                        float(match.group(1)) if match else None,
                    )
                else:
                    console.print(
                        f"[red]NO PING REPLY[/red] | {target}"
                    )
                    save_result(
                        target,
                        "REACHABILITY",
                        "OFFLINE",
                        "No ping response received",
                    )

            except ValueError:
                console.print(
                    "[red]Invalid IPv4 address. "
                    "Example: 172.19.55.43[/red]"
                )
            except subprocess.TimeoutExpired:
                console.print(
                    "[red]Ping timed out for this device.[/red]"
                )

        
        elif choice == "3":
            import subprocess
            import ipaddress
            import platform
            from rich.table import Table

            if platform.system() != "Windows":
                console.print(
                    "[red]This topology version is configured for Windows.[/red]"
                )
            else:
                target = input(
                    "Enter destination IPv4 address or hostname: "
                ).strip()

                try:
                    # Accept an IPv4 address or resolve a hostname
                    try:
                        ipaddress.IPv4Address(target)
                        destination = target
                    except ValueError:
                        import socket
                        destination = socket.gethostbyname(target)

                    console.print(
                        f"[cyan]Tracing route to {destination}...[/cyan]"
                    )

                    result = subprocess.run(
                        ["tracert", "-d", "-h", "12", "-w", "1000", destination],
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )

                    table = Table(title=f"Route to {destination}")
                    table.add_column("Hop")
                    table.add_column("Route Details")

                    for line in result.stdout.splitlines():
                        stripped = line.strip()
                        if stripped:
                            table.add_row(
                                stripped.split()[0]
                                if stripped.split()[0].isdigit()
                                else "-",
                                stripped,
                            )

                    if result.returncode == 0 and result.stdout.strip():
                        console.print(table)

                        save_result(
                            destination,
                            "TOPOLOGY",
                            "SUCCESS",
                            result.stdout.strip(),
                        )

                    else:
                        console.print(
                            "[yellow]Traceroute did not return a complete result.[/yellow]"
                        )
                        if result.stderr.strip():
                            console.print(result.stderr)

                except (ValueError, OSError) as error:
                    console.print(f"[red]Could not trace route: {error}[/red]")
                except subprocess.TimeoutExpired:
                    console.print(
                        "[yellow]Traceroute timed out. Try again or use another destination.[/yellow]"
                    )

        
        elif choice == "4":
            import socket
            import ipaddress
            from rich.table import Table

            target = input(
                "Enter the IP address of your authorized test device: "
            ).strip()

            try:
                ipaddress.IPv4Address(target)

                ports = {
                    22: "SSH",
                    23: "Telnet",
                    53: "DNS",
                    80: "HTTP",
                    443: "HTTPS",
                    3306: "MySQL",
                    8080: "HTTP-Alt",
                }

                table = Table(title=f"Services on {target}")
                table.add_column("Port", justify="right")
                table.add_column("Service")
                table.add_column("Status")

                for port, service in ports.items():
                    try:
                        with socket.socket(
                            socket.AF_INET, socket.SOCK_STREAM
                        ) as sock:
                            sock.settimeout(0.5)
                            result = sock.connect_ex((target, port))

                        if result == 0:
                            status = "[green]OPEN[/green]"
                        else:
                            status = "[red]CLOSED/FILTERED[/red]"

                    except OSError:
                        status = "[yellow]ERROR[/yellow]"

                    table.add_row(str(port), service, status)
                    save_result(
                        target,
                        "SERVICE_ENUMERATION",
                        status.replace("[green]", "").replace("[/green]", "")
                              .replace("[red]", "").replace("[/red]", "")
                              .replace("[yellow]", "").replace("[/yellow]", ""),
                        f"Port {port} - {service}",
                    )

                console.print(table)

            except ValueError:
                console.print(
                    "[red]Invalid IPv4 address. "
                    "Example: 172.19.55.43[/red]"
                )

        
        elif choice == "5":
            import asyncio
            import ipaddress
            from rich.table import Table
            from pysnmp.hlapi.v3arch.asyncio import (
                SnmpEngine,
                CommunityData,
                UdpTransportTarget,
                ContextData,
                ObjectType,
                ObjectIdentity,
                get_cmd,
            )

            target = input("Enter SNMP device IPv4 address: ").strip()
            community = input("Enter SNMP v2c community: ").strip()

            try:
                ipaddress.IPv4Address(target)

                async def poll_snmp():
                    engine = SnmpEngine()

                    try:
                        transport = await UdpTransportTarget.create(
                            (target, 161),
                            timeout=2,
                            retries=1,
                        )

                        error_indication, error_status, error_index, var_binds = (
                            await get_cmd(
                                engine,
                                CommunityData(community, mpModel=1),
                                transport,
                                ContextData(),
                                ObjectType(
                                    ObjectIdentity("1.3.6.1.2.1.1.5.0")
                                ),
                                ObjectType(
                                    ObjectIdentity("1.3.6.1.2.1.1.1.0")
                                ),
                                ObjectType(
                                    ObjectIdentity("1.3.6.1.2.1.1.3.0")
                                ),
                            )
                        )

                        if error_indication:
                            console.print(
                                f"[red]SNMP error: {error_indication}[/red]"
                            )
                        elif error_status:
                            console.print(
                                f"[red]SNMP error: {error_status.prettyPrint()}[/red]"
                            )
                        else:
                            table = Table(title=f"SNMP Results: {target}")
                            table.add_column("Metric")
                            table.add_column("Value")

                            labels = [
                                "Device Name",
                                "System Description",
                                "System Uptime (ticks)",
                            ]

                            for label, var_bind in zip(labels, var_binds):
                                table.add_row(
                                    label,
                                    var_bind[1].prettyPrint(),
                                )

                            console.print(table)

                    finally:
                        engine.close_dispatcher()

                asyncio.run(poll_snmp())

            except ValueError:
                console.print(
                    "[red]Invalid IPv4 address. Example: 172.19.55.43[/red]"
                )
            except Exception as error:
                console.print(
                    f"[red]SNMP polling failed: {error}[/red]"
                )

        elif choice == "6":
            show_monitoring_dashboard()

        elif choice == "0":
            console.print("[green]Exiting NMS Dashboard. Goodbye![/green]")
            break
        else:
            console.print("[red]Invalid choice. Please enter a number from 0 to 5.[/red]")
        input("\nPress Enter to return to the menu...") 




if __name__ == "__main__":
    initialize_database()
    dashboard()

