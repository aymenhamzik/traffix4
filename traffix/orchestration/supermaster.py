"""
Supermaster: coordinates all masters. Runs the network agents every few seconds.

It never changes a light. It sends directives (emergency preparation, corridor
bias, weather timing) that each master weighs in its fixed priority order, and
it is the single entry point for the frontend (snapshot()).
"""
from ..agents.network.corridor import CorridorAgent
from ..agents.network.demand_forecast import DemandForecastAgent
from ..agents.network.emergency_route import EmergencyRouteAgent
from ..agents.network.incident_detection import IncidentDetectionAgent
from ..agents.network.notification import NotificationAgent
from ..agents.network.rerouting import ReroutingAgent
from ..agents.network.transit_monitor import TransitMonitorAgent
from ..agents.network.weather import WeatherAgent
from ..core import config


ABLATABLE = {"forecast": "forecast", "weather": "weather", "incident": "incident", "rerouting": "rerouting",
             "emergency-route": "emergency_route", "corridor": "corridor", "transit-monitor": "transit"}


class Supermaster:
    def __init__(self, ctx, disabled=()):
        self.ctx, self.bus = ctx, ctx.bus
        self.every = config.simulation()["supermaster_every"]
        self.forecast = DemandForecastAgent(ctx)
        self.weather = WeatherAgent(ctx)
        self.incident = IncidentDetectionAgent(ctx)
        self.rerouting = ReroutingAgent(ctx)
        self.emergency_route = EmergencyRouteAgent(ctx)
        self.corridor = CorridorAgent(ctx)
        self.transit = TransitMonitorAgent(ctx)
        self.notification = NotificationAgent(ctx)
        self.agents = [self.forecast, self.weather, self.incident, self.rerouting,
                       self.emergency_route, self.corridor, self.transit, self.notification]
        self.every_second = {self.incident, self.transit, self.emergency_route}
        self.disabled = set(disabled)                       # ablation: these agents never run
        off = {getattr(self, ABLATABLE[d]) for d in self.disabled}
        self.agents = [a for a in self.agents if a not in off]

    def step(self, now):
        slow_tick = int(now) % self.every == 0
        for a in self.agents:
            if a in self.every_second or slow_tick:
                a.step(now)
