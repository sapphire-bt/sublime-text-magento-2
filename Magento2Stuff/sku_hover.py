import base64
import re
import sublime
import sublime_plugin
import threading
import urllib

from Magento2Stuff.api import MagentoAPI
from Magento2Stuff.urls import Magento2StuffSettings
from Magento2Stuff.utils import Magento2Utils as utils

M2_URLS = Magento2StuffSettings()

class SkuHover(sublime_plugin.EventListener):
	CURRENT_VIEW = None

	SKU_PATTERNS = (
		r"^[0-9]{5}[a-z]{4}([a-z0-9]{2})?$",
		r"^D[0-9]{5}(SZ[0-9]+)?$",
	)

	def on_hover(self, view, point, hover_zone):
		if utils.get_setting("sku_lookup_on_hover"):
			if hover_zone == sublime.HOVER_TEXT:
				region = view.word(point)
				substr = view.substr(region)

				if self.is_sku(substr):
					self.CURRENT_VIEW = view

					thread = threading.Thread(target = self.get_sku_info, args = (substr, view, point, self.show_sku_hover))
					thread.start()

	def is_sku(self, text):
		for p in self.SKU_PATTERNS:
			pattern = re.compile(p, re.IGNORECASE)

			if pattern.search(text):
				return True

		return False

	def get_sku_info(self, sku, view, point, callback):
		response = MagentoAPI.request("GET", "products/{}".format(sku))
		callback(view, point, response)

	def show_sku_hover(self, view, point, response):
		product_html = self.get_sku_html_summary(response)

		# show_popup params:
		# content, <flags>, <location>, <max_width>, <max_height>, <on_navigate>, <on_hide>
		view.show_popup(
			product_html,
			sublime.HIDE_ON_MOUSE_MOVE_AWAY,
			point,
			500,
			500,
			lambda href: self.handle_sku_popup_link(href, response)
		)

	def get_sku_html_summary(self, response):
		image_data = None
		site_url   = None
		admin_url  = M2_URLS.ADMIN_URL_PRODUCT.format(response["id"])

		for attr in response["custom_attributes"]:
			if attr["attribute_code"] == "image":
				image_data = self.get_image(M2_URLS.CATALOG_URL + attr["value"])

			elif attr["attribute_code"] == "url_key":
				site_url = M2_URLS.BASE_URL + attr["value"]

		response["admin_url"] = admin_url

		if site_url != None:
			response["site_url"] = site_url

		return """
			<body id="sku-output">
				<style>
					body {{
						font-family: Segoe UI, sans-serif;
						line-height: 1.5;
					}}
					h3 {{
						line-height: 1.2;
						margin: 0;
					}}
					.debug {{
						font-size: 0.85rem;
					}}
					.gallery {{
						margin-top: 0.5rem;
					}}
					.product-name {{
						margin-bottom: 0.5rem;
					}}
				</style>

				<div class="product-name">
					<h3>{name}</h3>
					<a class="debug" href="debug:{sku}"><em>debug</em></a>
				</div>
				<div>
					ID: <a href="copy:{entity_id}">{entity_id}</a>
				</div>
				<div>
					SKU: <a href="copy:{sku}">{sku}</a>
				</div>
				<div>
					Site URL: <a href="open:{site_url}">open</a> | <a href="copy:{site_url}">copy</a>
				</div>
				<div>
					Magento URL: <a href="open:{admin_url}">open</a> | <a href="copy:{admin_url}">copy</a>
				</div>
				<div>
					Type: {type_id}
				</div>
				<div>
					Price: £{price:,.2f}
				</div>
				<div>
					Updated: {updated_at}
				</div>

				<div class="gallery">
					<img src="data:image/jpg;base64,{image_data}" width="150" height="150" />
				</div>
			</body>
		""".format(
			name       = response["name"],
			entity_id  = response["id"],
			sku        = response["sku"],
			site_url   = site_url if site_url != None else "",
			admin_url  = admin_url,
			type_id    = response["type_id"],
			price      = float(response["price"]),
			updated_at = response["updated_at"],
			image_data = image_data if image_data != None else "",
		)

	def get_image(self, url):
		req = urllib.request.Request(url = url, method = "GET")

		response = urllib.request.urlopen(req).read()

		return base64.b64encode(response).decode()

	def handle_sku_popup_link(self, href, response):
		command, value = self.parse_href_action(href)

		if command == "copy":
			sublime.set_clipboard(value)
			utils.log('copied value to clipboard: "{}"'.format(value))

		elif command == "open":
			utils.open_url(value)

		elif command == "debug":
			utils.dump_as_json(response)

		else:
			utils.log('unrecognised command: "{}"'.format(command))

		if utils.get_setting("close_popup_after_click") and self.CURRENT_VIEW != None:
			self.CURRENT_VIEW.hide_popup()

	def parse_href_action(self, href, delim = ":"):
		delim_pos = href.find(delim)
		command   = href[:delim_pos]
		value     = href[delim_pos + len(delim):]

		return (command, value,)