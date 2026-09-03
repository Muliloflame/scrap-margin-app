"""
Scrap Metal Margin Calculator
------------------------------
A Kivy app (runs on Android via Buildozer, and on desktop for testing)
that converts a ZAR/kg scrap metal selling price sheet into ZMW,
lets you enter your buy price and weight per product, deducts a
per-kg transport cost, and totals your profit, spend, and transport
across everything you've weighed in.

Data (buy prices, kg entered, exchange rate, transport rate) is
saved to a local JSON file so it survives closing the app.
"""

import json
import os
import threading
import urllib.request
import urllib.error

from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line, Ellipse
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.clock import Clock

# ---------------------------------------------------------------------------
# Price sheet data: (name, ZAR per kg, optional note)
# ---------------------------------------------------------------------------
DATA = [
    ("Copper", "e0602b", [
        ("CU S/B", 228.00, "No tin lugs"),
        ("1A Wire", 223.00, None),
        ("Mix Copper", 210.00, None),
        ("CU Solids", 210.00, None),
        ("Tin Copper", 210.00, None),
        ("Brazery - Clean", 183.00, None),
        ("Brazery - Contains Steel", 168.00, "Steel / plastic / rubber / sand"),
        ("CU Shaving", 178.00, None),
        ("CU Elements", 43.00, None),
        ("Copper Rads", 122.00, None),
        ("Copper Rads Small", 111.00, None),
    ]),
    ("Brass & Gunmetal", "c9a227", [
        ("GM Solid", 182.00, None),
        ("GM Shaving", 177.00, None),
        ("GM Leaded", 177.00, None),
        ("Crown Wheel", 211.00, None),
        ("Heavy Brass", 124.00, "No steel / plastic attachments"),
        ("Heavy Brass - Contains", 114.00, "Steel / plastic / rubber / sand"),
        ("Brass Shav", 107.00, None),
        ("Light Brass", 107.00, None),
        ("Cart Case Small", 120.00, None),
        ("Cart Case Large", 101.00, None),
        ("Ali Bronze", 111.00, None),
        ("A.B. Shaving", 108.00, None),
    ]),
    ("Aluminium", "8b98a3", [
        ("Ali Cast Clean", 36.00, "Sorted and clean"),
        ("Ali Old Roll Clean", 34.00, "Sorted and clean"),
        ("Extrusion", 49.00, None),
        ("Ali Wire", 33.00, None),
        ("Ali Shaving", 19.00, None),
        ("Ali Cans", 26.00, None),
        ("Ali CU Rads", 105.00, None),
        ("Ali Litho", 49.00, None),
        ("Ali Rims", 43.00, None),
        ("Ali Rads", 26.00, None),
        ("Ali Foil / Air Legs", 6.00, None),
        ("Mag Ali", 2.00, None),
        ("Ali Uncl Ironing Base", 2.00, None),
    ]),
    ("Lead, Zinc & Batteries", "8b98a3", [
        ("Lead Cable Clean", 24.00, None),
        ("Lead Hard", 21.00, None),
        ("Lead Wheel Weights", 17.00, None),
        ("Batteries", 12.00, None),
        ("Zinc Clean", 27.00, "No steel"),
        ("Zinc Dross", 6.00, None),
    ]),
    ("Stainless Steel", "8b98a3", [
        ("Stainless 304", 16.00, None),
        ("Stainless 316", 31.00, None),
        ("Stainless 310", 37.00, None),
        ("S/S Shav", 9.00, None),
        ("3CR12 - S/S 430 Magn", 2.00, None),
        ("S/S Elements", 1.00, None),
        ("S/S Nitronic", 1.00, None),
    ]),
    ("Exotic Metals", "a678c9", [
        ("Nic SQ", 200.00, None),
        ("Nic Cush", 170.00, None),
        ("Tin", 520.00, None),
        ("Moly", 570.00, None),
        ("Elec Motors", 2.00, None),
        ("Tung Tooling", 1200.00, None),
        ("Tung Wear No Co/No Ni", 1030.00, None),
        ("Tung Wear Unclean", 970.00, None),
        ("Tung CL Mine", 1260.00, None),
        ("Tung UCL Mine", 1200.00, None),
    ]),
]

# These items are bought and sold locally in Kwacha (no ZAR leg, no
# transport), so their buy/sell prices are entered directly in ZK and
# their profit skips the transport deduction and the settlement slip.
DIRECT_ZK_NAMES = {"Ali Cans", "Ali Cast Clean", "Ali Old Roll Clean"}

BG = (0.10, 0.10, 0.11, 1)
PANEL = (0.14, 0.14, 0.15, 1)
LINE = (0.22, 0.22, 0.24, 1)
INK = (0.93, 0.91, 0.89, 1)
INK_DIM = (0.61, 0.59, 0.55, 1)
GOOD = (0.30, 0.60, 0.42, 1)
BAD = (0.82, 0.28, 0.23, 1)
AMBER = (0.94, 0.66, 0.24, 1)
LED_BG = (0.05, 0.06, 0.05, 1)

DATA_FILE = "scrap_app_data.json"


def hex_to_rgba(h):
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    return (r, g, b, 1)


def fmt(n):
    try:
        return f"{n:,.2f}"
    except (TypeError, ValueError):
        return "—"


class ColoredBox(BoxLayout):
    """A BoxLayout with a flat background color, optional rounded
    corners, and an optional accent border."""

    def __init__(self, bg=PANEL, radius=0, border_color=None, border_width=1.3, **kwargs):
        super().__init__(**kwargs)
        self._radius = radius
        with self.canvas.before:
            Color(*bg)
            if radius:
                self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                               radius=[radius])
            else:
                self._rect = Rectangle(pos=self.pos, size=self.size)
            self._border_line = None
            if border_color:
                Color(*border_color)
                if radius:
                    self._border_line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                                              width=border_width)
                else:
                    self._border_line = Line(rectangle=(self.x, self.y, self.width, self.height),
                                              width=border_width)
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        if self._border_line:
            if self._radius:
                self._border_line.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)
            else:
                self._border_line.rectangle = (self.x, self.y, self.width, self.height)


class CategoryHeader(ColoredBox):
    def __init__(self, name, color_hex, count, **kwargs):
        super().__init__(bg=PANEL, radius=dp(10), orientation="horizontal",
                          size_hint_y=None, height=dp(44),
                          padding=(dp(14), 0), **kwargs)
        dot = Widget(size_hint_x=None, width=dp(14))
        color_rgba = hex_to_rgba(color_hex)
        with dot.canvas:
            Color(*color_rgba)
            dot._circle = Ellipse(pos=dot.pos, size=(dp(11), dp(11)))

        def _update_dot(w, *_):
            cx = w.x
            cy = w.y + (w.height - dp(11)) / 2
            w._circle.pos = (cx, cy)
            w._circle.size = (dp(11), dp(11))

        dot.bind(pos=_update_dot, size=_update_dot)
        self.add_widget(dot)
        spacer = Widget(size_hint_x=None, width=dp(8))
        self.add_widget(spacer)
        label = Label(
            text=f"{name}  [size=11][color=9b968d]({count})[/color][/size]",
            markup=True, color=INK, bold=True, halign="left", valign="middle",
            size_hint_x=1,
        )
        label.bind(size=label.setter("text_size"))
        self.add_widget(label)


class ProductCard(ColoredBox):
    """One product: name/price header, buy+kg inputs, computed results.

    For DIRECT_ZK_NAMES items, both buy and sell are entered directly
    in Kwacha and no transport is deducted from the margin."""

    def __init__(self, app, cat, name, zar, note, accent_hex="8b98a3", **kwargs):
        self.direct = name in DIRECT_ZK_NAMES
        super().__init__(bg=PANEL, radius=dp(10), border_color=LINE, border_width=1,
                          orientation="vertical",
                          size_hint_y=None, height=dp(118),
                          padding=(dp(12), dp(8)), spacing=dp(4), **kwargs)
        self.app = app
        self.zar = zar
        self.pid = f"{cat}__{name}".lower().replace(" ", "-").replace("/", "-")
        self.accent = hex_to_rgba(accent_hex)

        # Row 1: name + ZAR price (or "local ZK" note for direct items)
        top = BoxLayout(size_hint_y=None, height=dp(20))
        note_text = note
        if self.direct:
            note_text = "Local Kwacha trade — no transport" if not note else f"{note} · Local Kwacha trade — no transport"
        name_text = name if not note_text else f"{name}  [size=10][color=c9a227]{note_text}[/color][/size]"
        name_lbl = Label(text=name_text, markup=True, color=INK, bold=True,
                          halign="left", valign="middle", size_hint_x=0.7)
        name_lbl.bind(size=name_lbl.setter("text_size"))
        price_text = "Priced in ZK" if self.direct else f"R{fmt(zar)}/kg"
        zar_lbl = Label(text=price_text, color=INK_DIM, halign="right",
                         valign="middle", size_hint_x=0.3)
        zar_lbl.bind(size=zar_lbl.setter("text_size"))
        top.add_widget(name_lbl)
        top.add_widget(zar_lbl)
        self.add_widget(top)

        # Row 2: buy price input + kg input (+ sell input for direct items)
        mid = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        self.buy_input = TextInput(
            hint_text="Buy ZK/kg", input_filter="float", multiline=False,
            font_size=dp(13), padding=[dp(8), dp(8)],
            background_color=LED_BG, foreground_color=AMBER,
            hint_text_color=INK_DIM, cursor_color=AMBER,
        )
        self.buy_input.text = str(app.buy_prices.get(self.pid, ""))
        self.buy_input.bind(text=self.on_change)
        mid.add_widget(self.buy_input)

        self.sell_input = None
        if self.direct:
            self.sell_input = TextInput(
                hint_text="Sell ZK/kg", input_filter="float", multiline=False,
                font_size=dp(13), padding=[dp(8), dp(8)],
                background_color=LED_BG, foreground_color=AMBER,
                hint_text_color=INK_DIM, cursor_color=AMBER,
            )
            self.sell_input.text = str(app.sell_prices_direct.get(self.pid, ""))
            self.sell_input.bind(text=self.on_change)
            mid.add_widget(self.sell_input)

        self.kg_input = TextInput(
            hint_text="Kg", input_filter="float", multiline=False,
            font_size=dp(13), padding=[dp(8), dp(8)],
            background_color=LED_BG, foreground_color=AMBER,
            hint_text_color=INK_DIM, cursor_color=AMBER,
        )
        self.kg_input.text = str(app.kg_amounts.get(self.pid, ""))
        self.kg_input.bind(text=self.on_change)
        mid.add_widget(self.kg_input)
        self.add_widget(mid)

        # Row 3: computed results
        bottom = BoxLayout(size_hint_y=None, height=dp(20))
        self.sell_lbl = Label(text="—", color=INK_DIM, font_size=dp(11),
                               halign="left", valign="middle", size_hint_x=0.33)
        self.pct_lbl = Label(text="—", color=INK_DIM, font_size=dp(11),
                              halign="center", valign="middle", size_hint_x=0.33)
        self.total_lbl = Label(text="—", color=INK_DIM, font_size=dp(11), bold=True,
                                halign="right", valign="middle", size_hint_x=0.34)
        for lbl in (self.sell_lbl, self.pct_lbl, self.total_lbl):
            lbl.bind(size=lbl.setter("text_size"))
        bottom.add_widget(self.sell_lbl)
        bottom.add_widget(self.pct_lbl)
        bottom.add_widget(self.total_lbl)
        self.add_widget(bottom)

        self.recompute()

    def on_change(self, *_):
        try:
            self.app.buy_prices[self.pid] = float(self.buy_input.text)
        except ValueError:
            self.app.buy_prices.pop(self.pid, None)
        try:
            self.app.kg_amounts[self.pid] = float(self.kg_input.text)
        except ValueError:
            self.app.kg_amounts.pop(self.pid, None)
        if self.direct and self.sell_input is not None:
            try:
                self.app.sell_prices_direct[self.pid] = float(self.sell_input.text)
            except ValueError:
                self.app.sell_prices_direct.pop(self.pid, None)
        self.app.save_data()
        self.app.recompute_all()

    def recompute(self):
        """Returns (margin, kg, spent, transport, settlement_amount) —
        settlement_amount is None for direct-ZK items, since they have
        no ZAR leg and don't belong on the settlement slip."""
        fx = self.app.fx_rate
        transport_per_kg = self.app.transport_rate * fx

        try:
            buy = float(self.buy_input.text)
        except ValueError:
            buy = None
        try:
            kg = float(self.kg_input.text)
        except ValueError:
            kg = None

        if self.direct:
            try:
                sell = float(self.sell_input.text)
            except (ValueError, AttributeError):
                sell = None
            self.sell_lbl.text = f"Sell ZK{fmt(sell)}" if sell is not None else "Sell ZK—"
        else:
            sell = self.zar * fx
            self.sell_lbl.text = f"Sell ZK{fmt(sell)}"

        if buy is not None and sell is not None:
            margin = sell - buy if self.direct else sell - buy - transport_per_kg
            pct = (margin / sell * 100) if sell else 0
            self.pct_lbl.text = f"{pct:+.1f}%"
            self.pct_lbl.color = GOOD if pct > 0 else BAD if pct < 0 else INK_DIM
        else:
            margin = None
            self.pct_lbl.text = "—"
            self.pct_lbl.color = INK_DIM

        if margin is not None and kg is not None:
            line_total = margin * kg
            self.total_lbl.text = f"{'+' if line_total >= 0 else ''}ZK{fmt(line_total)}"
            self.total_lbl.color = GOOD if line_total > 0 else BAD if line_total < 0 else INK_DIM
            row_transport = 0.0 if self.direct else transport_per_kg * kg
            return margin, kg, buy * kg, row_transport
        else:
            self.total_lbl.text = "—"
            self.total_lbl.color = INK_DIM
            return None, None, None, None


class RootWidget(ColoredBox):
    pass


class ScrapApp(App):
    def build(self):
        Window.clearcolor = BG
        self.title = "Scrap Metal Margin Calculator"

        self.fx_rate = 1.167
        self.transport_rate = 10.5
        self.cash_charge_pct = 1.5
        self.advance_deduct = 0.0
        self.buy_prices = {}
        self.sell_prices_direct = {}
        self.kg_amounts = {}
        self.slip_meta = {"date": "", "buyer": "", "docket": "", "seller": ""}
        self.bridge_url = "http://127.0.0.1:5000/rate"
        self.product_cards = []

        self.load_data()

        root = ColoredBox(bg=BG, orientation="vertical", padding=(dp(6), 0, dp(6), dp(6)))

        # --- Header ---
        header = ColoredBox(bg=BG, orientation="vertical", size_hint_y=None,
                             height=dp(60), padding=(dp(14), dp(6)), spacing=dp(2))
        title_row = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(8))
        brand_dot = Widget(size_hint_x=None, width=dp(8))
        with brand_dot.canvas:
            Color(*hex_to_rgba("c1622b"))
            brand_dot._circle = Ellipse(pos=brand_dot.pos, size=(dp(8), dp(8)))

        def _update_brand_dot(w, *_):
            w._circle.pos = (w.x, w.y + (w.height - dp(8)) / 2)
            w._circle.size = (dp(8), dp(8))

        brand_dot.bind(pos=_update_brand_dot, size=_update_brand_dot)
        title_row.add_widget(brand_dot)
        title = Label(text="Scrap Metal Margin Calculator", color=INK, bold=True,
                      font_size=dp(18), halign="left", valign="middle")
        title.bind(size=title.setter("text_size"))
        title_row.add_widget(title)
        header.add_widget(title_row)
        sub = Label(text="ZAR sheet -> ZMW · buy price, weight & transport · settlement slip",
                    color=INK_DIM, font_size=dp(11), halign="left", valign="middle")
        sub.bind(size=sub.setter("text_size"))
        header.add_widget(sub)
        underline = Widget(size_hint_y=None, height=dp(2))
        with underline.canvas:
            Color(*hex_to_rgba("c1622b"))
            underline._rect = Rectangle(pos=underline.pos, size=underline.size)
        underline.bind(pos=lambda w, *_: setattr(w._rect, "pos", w.pos))
        underline.bind(size=lambda w, *_: setattr(w._rect, "size", w.size))
        header.add_widget(underline)
        root.add_widget(header)

        # --- Control deck: FX rate + transport rate ---
        controls = BoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(68), padding=(dp(12), dp(8)), spacing=dp(10))

        fx_box = ColoredBox(bg=PANEL, radius=dp(10), border_color=LINE, border_width=1,
                             orientation="vertical", padding=(dp(10), dp(8)))
        fx_label = Label(text="ZAR -> ZMW rate", color=INK_DIM, font_size=dp(10),
                          size_hint_y=None, height=dp(16), halign="left", valign="middle")
        fx_label.bind(size=fx_label.setter("text_size"))
        self.fx_input = TextInput(text=str(self.fx_rate), input_filter="float",
                                   multiline=False, font_size=dp(16),
                                   foreground_color=AMBER, background_color=(0, 0, 0, 0),
                                   cursor_color=AMBER)
        self.fx_input.bind(text=self.on_fx_change)
        fx_box.add_widget(fx_label)
        fx_box.add_widget(self.fx_input)

        transport_box = ColoredBox(bg=PANEL, radius=dp(10), border_color=LINE, border_width=1,
                                    orientation="vertical", padding=(dp(10), dp(8)))
        transport_label = Label(text="Transport R/kg", color=INK_DIM, font_size=dp(10),
                                 size_hint_y=None, height=dp(16), halign="left", valign="middle")
        transport_label.bind(size=transport_label.setter("text_size"))
        self.transport_input = TextInput(text=str(self.transport_rate), input_filter="float",
                                          multiline=False, font_size=dp(16),
                                          foreground_color=AMBER, background_color=(0, 0, 0, 0),
                                          cursor_color=AMBER)
        self.transport_input.bind(text=self.on_transport_change)
        transport_box.add_widget(transport_label)
        transport_box.add_widget(self.transport_input)

        controls.add_widget(fx_box)
        controls.add_widget(transport_box)
        root.add_widget(controls)

        # --- Live forex bridge panel ---
        live_panel = ColoredBox(bg=PANEL, radius=dp(10), border_color=LINE, border_width=1,
                                 orientation="vertical", size_hint_y=None, height=dp(92),
                                 padding=(dp(12), dp(8)), spacing=dp(4))
        live_row1 = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        bridge_label = Label(text="Bridge:", color=INK_DIM, font_size=dp(11),
                              size_hint_x=None, width=dp(52), halign="left", valign="middle")
        bridge_label.bind(size=bridge_label.setter("text_size"))
        self.bridge_url_input = TextInput(text=self.bridge_url, multiline=False,
                                           font_size=dp(11), size_hint_x=0.62,
                                           background_color=LED_BG, foreground_color=INK_DIM,
                                           cursor_color=AMBER)
        self.bridge_url_input.bind(text=self.on_bridge_url_change)
        fetch_btn = Button(text="Fetch live rate", size_hint_x=0.38, font_size=dp(11),
                            background_normal="", background_color=hex_to_rgba("c1622b"),
                            color=(1, 1, 1, 1))
        fetch_btn.bind(on_release=self.fetch_live_rate)
        live_row1.add_widget(bridge_label)
        live_row1.add_widget(self.bridge_url_input)
        live_row1.add_widget(fetch_btn)

        live_row2 = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(6))
        self.live_dot = Widget(size_hint_x=None, width=dp(8))
        with self.live_dot.canvas:
            self._live_dot_color = Color(*INK_DIM)
            self.live_dot._circle = Ellipse(pos=self.live_dot.pos, size=(dp(8), dp(8)))

        def _update_live_dot(w, *_):
            w._circle.pos = (w.x, w.y + (w.height - dp(8)) / 2)
            w._circle.size = (dp(8), dp(8))

        self.live_dot.bind(pos=_update_live_dot, size=_update_live_dot)
        self.live_status_label = Label(text="Not fetched yet", color=INK_DIM, font_size=dp(10.5),
                                        halign="left", valign="middle")
        self.live_status_label.bind(size=self.live_status_label.setter("text_size"))
        live_row2.add_widget(self.live_dot)
        live_row2.add_widget(self.live_status_label)

        live_panel.add_widget(live_row1)
        live_panel.add_widget(live_row2)
        root.add_widget(live_panel)

        # --- Scrollable product list ---
        scroll = ScrollView(size_hint=(1, 1))
        self.list_layout = GridLayout(cols=1, size_hint_y=None, spacing=dp(4),
                                       padding=(0, dp(4)))
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))

        for cat, color_hex, items in DATA:
            self.list_layout.add_widget(CategoryHeader(cat, color_hex, len(items)))
            for name, zar, note in items:
                card = ProductCard(self, cat, name, zar, note, accent_hex=color_hex)
                self.product_cards.append(card)
                self.list_layout.add_widget(card)

        self.list_layout.add_widget(self._build_settlement_slip())

        scroll.add_widget(self.list_layout)
        root.add_widget(scroll)

        # --- Totals bar ---
        self.totals_bar = ColoredBox(bg=PANEL, radius=dp(12), border_color=hex_to_rgba("c1622b"),
                                      border_width=1.4, orientation="vertical", size_hint_y=None,
                                      height=dp(84), padding=(dp(14), dp(8)), spacing=dp(2))
        self.grand_label = Label(text="ZK0.00", color=AMBER, bold=True, font_size=dp(24),
                                  halign="left", valign="middle", size_hint_y=None, height=dp(34))
        self.grand_label.bind(size=self.grand_label.setter("text_size"))
        self.breakdown_label = Label(text="0.00 kg · ZK0.00 spent · ZK0.00 (R0.00) transport",
                                      color=INK_DIM, font_size=dp(11),
                                      halign="left", valign="middle",
                                      size_hint_y=None, height=dp(30))
        self.breakdown_label.bind(size=self.breakdown_label.setter("text_size"))

        clear_btn = Button(text="Clear kg entries", size_hint_y=None, height=dp(30),
                            background_color=(0, 0, 0, 0), color=INK_DIM, font_size=dp(11))
        clear_btn.bind(on_release=self.clear_kg)

        self.totals_bar.add_widget(self.grand_label)
        self.totals_bar.add_widget(self.breakdown_label)
        self.totals_bar.add_widget(clear_btn)
        root.add_widget(self.totals_bar)

        Clock.schedule_once(lambda dt: self.recompute_all(), 0)
        return root

    def _build_settlement_slip(self):
        """Builds the 'settlement slip' panel: subtotal, cash charges,
        advance deduct, and transport deduct on the kg already entered
        above, giving a final balance in Rand and its Kwacha equivalent."""
        panel = ColoredBox(bg=PANEL, radius=dp(12), border_color=LINE, border_width=1,
                            orientation="vertical", size_hint_y=None,
                            height=dp(340), padding=(dp(12), dp(10)), spacing=dp(6))

        title = Label(text="Settlement Slip", color=INK, bold=True, font_size=dp(15),
                      size_hint_y=None, height=dp(22), halign="left", valign="middle")
        title.bind(size=title.setter("text_size"))
        panel.add_widget(title)

        hint = Label(text="Uses the kg entered above, priced at today's sheet",
                     color=INK_DIM, font_size=dp(10), size_hint_y=None, height=dp(16),
                     halign="left", valign="middle")
        hint.bind(size=hint.setter("text_size"))
        panel.add_widget(hint)

        # Docket meta fields, 2x2 grid
        meta_grid = GridLayout(cols=2, size_hint_y=None, height=dp(76), spacing=dp(6))
        self.slip_date_input = TextInput(hint_text="Date", text=self.slip_meta["date"],
                                          multiline=False, font_size=dp(12))
        self.slip_buyer_input = TextInput(hint_text="Buyer / depot", text=self.slip_meta["buyer"],
                                           multiline=False, font_size=dp(12))
        self.slip_docket_input = TextInput(hint_text="Docket #", text=self.slip_meta["docket"],
                                            multiline=False, font_size=dp(12))
        self.slip_seller_input = TextInput(hint_text="Seller name", text=self.slip_meta["seller"],
                                            multiline=False, font_size=dp(12))
        for inp, key in ((self.slip_date_input, "date"), (self.slip_buyer_input, "buyer"),
                         (self.slip_docket_input, "docket"), (self.slip_seller_input, "seller")):
            inp.bind(text=self._make_meta_handler(key))
            meta_grid.add_widget(inp)
        panel.add_widget(meta_grid)

        def make_row(label_text):
            row = BoxLayout(size_hint_y=None, height=dp(26))
            lbl = Label(text=label_text, color=INK_DIM, font_size=dp(12),
                        halign="left", valign="middle", size_hint_x=0.5)
            lbl.bind(size=lbl.setter("text_size"))
            val = Label(text="—", color=INK, font_size=dp(12),
                        halign="right", valign="middle", size_hint_x=0.5)
            val.bind(size=val.setter("text_size"))
            row.add_widget(lbl)
            row.add_widget(val)
            panel.add_widget(row)
            return val

        self.slip_subtotal_label = make_row("Subtotal (ZAR)")

        # Cash charge row with its own % input
        cash_row = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(4))
        cash_lbl = Label(text="Cash charges", color=INK_DIM, font_size=dp(12),
                          halign="left", valign="middle", size_hint_x=0.4)
        cash_lbl.bind(size=cash_lbl.setter("text_size"))
        self.cash_pct_input = TextInput(text=str(self.cash_charge_pct), input_filter="float",
                                         multiline=False, font_size=dp(12), size_hint_x=0.2)
        self.cash_pct_input.bind(text=self.on_cash_pct_change)
        self.slip_cash_charge_label = Label(text="- R0.00", color=BAD, font_size=dp(12),
                                             halign="right", valign="middle", size_hint_x=0.4)
        self.slip_cash_charge_label.bind(size=self.slip_cash_charge_label.setter("text_size"))
        cash_row.add_widget(cash_lbl)
        cash_row.add_widget(self.cash_pct_input)
        cash_row.add_widget(self.slip_cash_charge_label)
        panel.add_widget(cash_row)

        # Advance deduct row with its own amount input
        adv_row = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(4))
        adv_lbl = Label(text="Advance deduct (R)", color=INK_DIM, font_size=dp(12),
                         halign="left", valign="middle", size_hint_x=0.6)
        adv_lbl.bind(size=adv_lbl.setter("text_size"))
        self.advance_input = TextInput(text=str(self.advance_deduct), input_filter="float",
                                        multiline=False, font_size=dp(12), size_hint_x=0.4)
        self.advance_input.bind(text=self.on_advance_change)
        adv_row.add_widget(adv_lbl)
        adv_row.add_widget(self.advance_input)
        panel.add_widget(adv_row)

        self.slip_transport_label = make_row("Transport deduct")

        # Balance rows
        bal_row = BoxLayout(size_hint_y=None, height=dp(30))
        bal_lbl = Label(text="Balance", color=INK, bold=True, font_size=dp(15),
                         halign="left", valign="middle", size_hint_x=0.5)
        bal_lbl.bind(size=bal_lbl.setter("text_size"))
        self.slip_balance_r_label = Label(text="R0.00", color=AMBER, bold=True, font_size=dp(15),
                                           halign="right", valign="middle", size_hint_x=0.5)
        self.slip_balance_r_label.bind(size=self.slip_balance_r_label.setter("text_size"))
        bal_row.add_widget(bal_lbl)
        bal_row.add_widget(self.slip_balance_r_label)
        panel.add_widget(bal_row)

        bal_zk_row = BoxLayout(size_hint_y=None, height=dp(20))
        bal_zk_lbl = Label(text="Balance in Kwacha", color=INK_DIM, font_size=dp(11),
                            halign="left", valign="middle", size_hint_x=0.5)
        bal_zk_lbl.bind(size=bal_zk_lbl.setter("text_size"))
        self.slip_balance_zk_label = Label(text="ZK0.00", color=(0.79, 0.64, 0.15, 1), bold=True,
                                            font_size=dp(11), halign="right", valign="middle",
                                            size_hint_x=0.5)
        self.slip_balance_zk_label.bind(size=self.slip_balance_zk_label.setter("text_size"))
        bal_zk_row.add_widget(bal_zk_lbl)
        bal_zk_row.add_widget(self.slip_balance_zk_label)
        panel.add_widget(bal_zk_row)

        return panel

    def _make_meta_handler(self, key):
        def handler(_, value):
            self.slip_meta[key] = value
            self.save_data()
        return handler

    def on_cash_pct_change(self, _, value):
        try:
            self.cash_charge_pct = float(value)
        except ValueError:
            return
        self.save_data()
        self.recompute_all()

    def on_advance_change(self, _, value):
        try:
            self.advance_deduct = float(value)
        except ValueError:
            self.advance_deduct = 0.0
        self.save_data()
        self.recompute_all()

    # -- Event handlers -----------------------------------------------
    def on_fx_change(self, _, value):
        try:
            self.fx_rate = float(value)
        except ValueError:
            return
        self.save_data()
        self.recompute_all()

    def on_transport_change(self, _, value):
        try:
            self.transport_rate = float(value)
        except ValueError:
            return
        self.save_data()
        self.recompute_all()

    def on_bridge_url_change(self, _, value):
        self.bridge_url = value.strip()
        self.save_data()

    def fetch_live_rate(self, *_):
        url = self.bridge_url.strip()
        self.live_status_label.text = "Contacting bridge..."
        self._live_dot_color.rgba = hex_to_rgba("c9a227")  # brass = loading

        def worker():
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                if not payload.get("effective_rate"):
                    raise ValueError(payload.get("error", "No rate returned"))
                Clock.schedule_once(lambda dt: self._apply_live_rate(payload))
            except urllib.error.URLError as e:
                msg = "Couldn't reach bridge — is forex_bridge.py running? (%s)" % e.reason
                Clock.schedule_once(lambda dt, m=msg: self._live_rate_failed(m))
            except Exception as e:
                msg = str(e)
                Clock.schedule_once(lambda dt, m=msg: self._live_rate_failed(m))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_live_rate(self, payload):
        rate = payload["effective_rate"]
        self.fx_rate = rate
        self.fx_input.text = str(rate)
        self.save_data()
        self.recompute_all()
        self._live_dot_color.rgba = GOOD
        banks = payload.get("banks", {})
        parts = [f"{b.get('bank_name', code)} {fmt(b.get('buying'))} buying" for code, b in banks.items()]
        self.live_status_label.text = f"Live: ZK{fmt(rate)}/R1 · " + " · ".join(parts)

    def _live_rate_failed(self, message):
        self._live_dot_color.rgba = BAD
        self.live_status_label.text = message

    def clear_kg(self, *_):
        self.kg_amounts = {}
        for card in self.product_cards:
            card.kg_input.text = ""
        self.save_data()
        self.recompute_all()

    def recompute_all(self):
        grand_total = 0.0
        spent_total = 0.0
        transport_total = 0.0
        transport_kg = 0.0
        kg_total = 0.0
        kg_lines = 0
        settlement_subtotal_r = 0.0
        settlement_kg = 0.0

        for card in self.product_cards:
            margin, kg, spent, transport = card.recompute()
            if margin is not None and kg is not None:
                grand_total += margin * kg
                spent_total += spent
                transport_total += transport
                kg_total += kg
                kg_lines += 1
                if not card.direct:
                    transport_kg += kg

            if not card.direct:
                try:
                    sett_kg = float(card.kg_input.text)
                except ValueError:
                    sett_kg = None
                if sett_kg is not None:
                    settlement_kg += sett_kg
                    settlement_subtotal_r += card.zar * sett_kg

        sign = "+" if grand_total >= 0 else ""
        self.grand_label.text = f"{sign}ZK{fmt(grand_total)}"
        self.grand_label.color = BAD if grand_total < 0 else AMBER

        transport_rand = transport_kg * self.transport_rate
        self.breakdown_label.text = (
            f"{fmt(kg_total)} kg across {kg_lines} product(s)  ·  "
            f"ZK{fmt(spent_total)} spent  ·  "
            f"ZK{fmt(transport_total)} (R{fmt(transport_rand)}) transport"
        )

        # --- Settlement slip ---
        cash_charge = settlement_subtotal_r * (self.cash_charge_pct / 100)
        settlement_transport_r = settlement_kg * self.transport_rate
        balance_r = settlement_subtotal_r - cash_charge - self.advance_deduct - settlement_transport_r
        balance_zk = balance_r * self.fx_rate

        self.slip_subtotal_label.text = f"R{fmt(settlement_subtotal_r)}"
        self.slip_cash_charge_label.text = f"- R{fmt(cash_charge)}"
        self.slip_transport_label.text = f"- R{fmt(settlement_transport_r)}"
        self.slip_balance_r_label.text = f"R{fmt(balance_r)}"
        self.slip_balance_r_label.color = BAD if balance_r < 0 else AMBER
        self.slip_balance_zk_label.text = f"ZK{fmt(balance_zk)}"

    # -- Persistence ----------------------------------------------------
    def data_path(self):
        return os.path.join(self.user_data_dir, DATA_FILE)

    def load_data(self):
        path = self.data_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                self.fx_rate = data.get("fx_rate", self.fx_rate)
                self.transport_rate = data.get("transport_rate", self.transport_rate)
                self.cash_charge_pct = data.get("cash_charge_pct", self.cash_charge_pct)
                self.advance_deduct = data.get("advance_deduct", self.advance_deduct)
                self.buy_prices = data.get("buy_prices", {})
                self.sell_prices_direct = data.get("sell_prices_direct", {})
                self.kg_amounts = data.get("kg_amounts", {})
                self.slip_meta.update(data.get("slip_meta", {}))
                self.bridge_url = data.get("bridge_url", self.bridge_url)
            except (json.JSONDecodeError, OSError):
                pass

    def save_data(self):
        path = self.data_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump({
                    "fx_rate": self.fx_rate,
                    "transport_rate": self.transport_rate,
                    "cash_charge_pct": self.cash_charge_pct,
                    "advance_deduct": self.advance_deduct,
                    "buy_prices": self.buy_prices,
                    "sell_prices_direct": self.sell_prices_direct,
                    "kg_amounts": self.kg_amounts,
                    "slip_meta": self.slip_meta,
                    "bridge_url": self.bridge_url,
                }, f)
        except OSError:
            pass


if __name__ == "__main__":
    ScrapApp().run()
