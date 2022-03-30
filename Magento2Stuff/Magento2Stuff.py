import json
import math
import os
import sublime
import sublime_plugin
import subprocess
import tempfile
import threading
import time
import urllib
import uuid

from datetime import datetime

from Magento2Stuff.api import MagentoAPI as api
from Magento2Stuff.country_codes import ISO_3166
from Magento2Stuff.urls import Magento2StuffSettings
from Magento2Stuff.utils import Magento2Utils as utils

M2_URLS = Magento2StuffSettings()

class Magento2StuffCommand(sublime_plugin.TextCommand):
	# Menu items
	MAIN_MENU_ITEMS = (
		"CMS pages",
		"CMS blocks",
		"Categories",
		"Products",
		"Product lookup",
		"Orders",
		"Change profile",
	)

	# Sub-menus
	CMS_PAGE_MENU_ITEMS = (
		"Insert page contents",
		"View in browser",
		"View in Magento",
		"Edit title...",
		"Edit identifier...",
		"Insert identifier",
		"{toggle} page",
		"Debug info",
	)

	CMS_BLOCK_MENU_ITEMS = (
		"Insert block contents",
		"View in Magento",
		"Edit title...",
		"Edit identifier...",
		"Insert identifier",
		"{toggle} block",
		"Debug info",
	)

	CATEGORY_MENU_ITEMS = (
		"Insert URL key",
		"View in browser",
		"View in Magento",
		"Debug info",
	)

	PRODUCT_MENU_ITEMS = (
		"View in browser",
		"View in Magento",
		"Debug info",
	)

	PRODUCT_LOOKUP_MENU_ITEMS = (
		"By SKU",
		"By ID",
	)

	ORDER_MENU_ITEMS = (
		"View in Magento",
		"Debug info",
	)

	API_RESPONSE_ITEMS = []

	SHEET_LIST = {}

	def run(self, edit, **args):
		if not args:
			self.show_main_menu()

		else:
			if "action" in args:
				action = args["action"]

				if action == "backup":
					backup_current_sheet()

				elif action == "list_backups":
					show_backup_files_list_menu()

				elif action == "go_to_admin_url":
					go_to_admin_url()

				elif action == "go_to_site_url":
					go_to_site_url()

				else:
					utils.log("unknown action: " + action)

	def show_main_menu(self):
		sublime.active_window().show_quick_panel(
			self.MAIN_MENU_ITEMS,
			lambda x: self.process_main_menu(self.MAIN_MENU_ITEMS[x]) if x != -1 else None,
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
			0,
			None,
			"Using " + M2_URLS.BASE_URL,
		)

	def process_main_menu(self, action):
		if action == "CMS pages":
			self.show_cms_resource_list_menu("cmsPage")

		elif action == "CMS blocks":
			self.show_cms_resource_list_menu("cmsBlock")

		elif action == "Categories":
			self.show_category_list_menu()

		elif action == "Products":
			self.show_product_list_menu()

		elif action == "Product lookup":
			self.show_product_lookup_menu()

		elif action == "Orders":
			self.show_order_list_menu()

		elif action == "Change profile":
			self.show_profile_list_menu()

	def show_cms_resource_list_menu(self, resource_type):
		page_size = utils.get_setting("page_size_cms")

		search_criteria = {
			"page_size": page_size,
			"sort_orders": [
				{
					"field": "update_time",
					"direction": "DESC",
				}
			],
		}

		fields = {
			"items": [
				"id",
				"title",
				"identifier",
				"active",
				"update_time",
			]
		}

		url = "{}/search".format(resource_type)

		response = api.request("GET", url, search_criteria = search_criteria, fields = fields)

		total_items = len(response["items"])

		# Construct CMS resource list menu
		menu_items = []

		for i in range(total_items):
			item = response["items"][i]

			quick_panel_item = sublime.QuickPanelItem(
				"{title} [{identifier}] | ID: {id}".format(title = item["title"], identifier = item["identifier"], id = item["id"]),
				"Last updated: " + format_datetime_str(item["update_time"]),
				"Enabled" if item["active"] else "DISABLED",
			)

			menu_items.append(quick_panel_item)

			# Add some extra data
			response["items"][i]["admin_url"] = get_admin_url(resource_type, item["id"])

			if resource_type == "cmsPage":
				response["items"][i]["site_url"] = get_site_url(item["identifier"])

		# Assign global variable with items for access after making a selection from the menu
		self.API_RESPONSE_ITEMS = response["items"]

		on_done = self.show_cms_page_menu if resource_type == "cmsPage" else self.show_cms_block_menu

		sublime.active_window().show_quick_panel(
			menu_items,
			on_done,
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

		if total_items >= page_size:
			utils.log("WARNING: number of API response items is greater than or equal to the page size ({})".format(page_size))

	def show_category_list_menu(self):
		page_size = utils.get_setting("page_size_categories")

		search_criteria = {
			"page_size": page_size,
			"sort_orders": [
				{
					"field": "updated_at",
					"direction": "DESC",
				}
			],
		}

		fields = {
			"items": [
				"id",
				"name",
				"is_active",
				"updated_at",
				{
					"custom_attributes": [
						"url_path",
					],
				},
			]
		}

		response = api.request("GET", "categories/list", search_criteria = search_criteria, fields = fields)

		total_items = len(response["items"])

		menu_items = []

		for i in range(total_items):
			item = response["items"][i]

			# Root catalog does not return this field...
			if "is_active" in item:
				status = "Enabled" if item["is_active"] else "DISABLED"
			else:
				status = "n/a"

			quick_panel_item = sublime.QuickPanelItem(
				"{name} | ID: {id}".format(name = item["name"], id = item["id"]),
				"Last updated: " + format_datetime_str(item["updated_at"]),
				status,
			)

			menu_items.append(quick_panel_item)

			# Add some extra data
			response["items"][i]["admin_url"] = get_admin_url("category", item["id"])

			for key in item["custom_attributes"]:
				attr = item["custom_attributes"][key]

				if attr["attribute_code"] == "url_path":
					response["items"][i]["site_url"] = M2_URLS.BASE_URL + attr["value"]
					response["items"][i]["url_path"] = attr["value"]

			if "site_url" not in response["items"][i]:
				response["items"][i]["site_url"] = M2_URLS.CATEGORY_ID_URL.format(item["id"])

		on_done = lambda x: self.show_category_menu(response["items"][x]) if x != -1 else None

		sublime.active_window().show_quick_panel(
			menu_items,
			on_done,
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

		if total_items >= page_size:
			utils.log("WARNING: number of API response items is greater than or equal to the page size ({})".format(page_size))

	def show_product_list_menu(self):
		page_size = utils.get_setting("page_size_products")

		search_criteria = {
			"page_size": page_size,
			"sort_orders": [
				{
					"field": "updated_at",
					"direction": "DESC",
				}
			],
		}

		fields = {
			"items": [
				"id",
				"name",
				"sku",
				"status",
				"type_id",
				"created_at",
				"updated_at",
				{
					"custom_attributes": [
						"url_key",
					],
				},
			]
		}

		response = api.request("GET", "products", search_criteria = search_criteria, fields = fields)

		total_items = len(response["items"])

		menu_items = []

		for i in range(total_items):
			item = response["items"][i]

			menu_items.append([
				"{name} | {sku} | ID: {id}".format(name = item["name"], sku = item["sku"], id = item["id"]),
				"Type: {type} | {status}".format(type = item["type_id"], status = "Enabled" if item["status"] == 1 else "DISABLED"),
				"Created: {} | Updated: {}".format(format_datetime_str(item["created_at"]), format_datetime_str(item["updated_at"])),
			])

			# Add some extra data
			response["items"][i]["admin_url"] = get_admin_url("product", item["id"])

			for key in item["custom_attributes"]:
				attr = item["custom_attributes"][key]

				if attr["attribute_code"] == "url_key":
					response["items"][i]["site_url"] = M2_URLS.BASE_URL + attr["value"]

		on_done = lambda x: self.show_product_menu(response["items"][x]) if x != -1 else None

		sublime.active_window().show_quick_panel(
			menu_items,
			on_done,
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

		if total_items >= page_size:
			utils.log("WARNING: number of API response items is greater than or equal to the page size ({})".format(page_size))

	def show_order_list_menu(self):
		page_size = utils.get_setting("page_size_orders")

		search_criteria = {
			"page_size": page_size,
			"sort_orders": [
				{
					"field": "created_at",
					"direction": "DESC",
				}
			],
		}
		fields = {
			"items": [
				"entity_id",
				"increment_id",
				"created_at",
				"grand_total",
				"status",
				"customer_is_guest",
				{
					"billing_address": [
						"firstname",
						"lastname",
						"city",
						"postcode",
						"country_id",
					],
					"extension_attributes": [
						"payment_additional_info",
					],
				},
			]
		}

		response = api.request("GET", "orders", search_criteria = search_criteria, fields = fields)

		total_items = len(response["items"])

		menu_items = []

		for i in range(total_items):
			item = response["items"][i]

			# Top line
			line_1 = "{} {} | {} | {}".format(
				item["billing_address"]["firstname"].strip(),
				item["billing_address"]["lastname"].strip(),
				item["increment_id"],
				item["entity_id"],
			)

			# Middle
			address_info = []

			if item["billing_address"]["city"]:
				address_info.append(item["billing_address"]["city"].strip())

			if item["billing_address"]["country_id"] != "GB":
				address_info.append(ISO_3166.alpha_2[item["billing_address"]["country_id"]])

			if item["billing_address"]["postcode"]:
				address_info.append(item["billing_address"]["postcode"])

			payment_method = None

			for info in item["extension_attributes"]["payment_additional_info"]:
				if info["key"] == "method_title":
					payment_method = info["value"]
					break

			line_2 = "Total £{:,.2f} | Guest: {} | Payment method: {} | {}".format(
				item["grand_total"],
				"yes" if item["customer_is_guest"] else "no",
				payment_method,
				", ".join(address_info),
			)

			# Bottom
			line_3 = format_datetime_str(item["created_at"])

			quick_panel_item = sublime.QuickPanelItem(
				line_1,
				[line_2, line_3],
			)

			menu_items.append(quick_panel_item)

			# Add some extra data
			response["items"][i]["admin_url"] = get_admin_url("order", item["entity_id"])

		on_done = lambda x: self.show_order_menu(response["items"][x]) if x != -1 else None

		sublime.active_window().show_quick_panel(
			menu_items,
			on_done,
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

	def show_profile_list_menu(self):
		profiles = utils.get_setting("profiles")

		if profiles:
			menu_items = []

			current_profile = utils.get_setting("current_profile")

			if current_profile == None:
				current_profile = 0

			for i, prof in enumerate(profiles):
				name = prof["name"]

				if current_profile == i:
					name += " (current)"

				menu_items.append([name, prof["base_url"]])

			on_done = lambda x: utils.set_setting("current_profile", x) if x != -1 else None

			sublime.active_window().show_quick_panel(
				menu_items,
				on_done,
				sublime.KEEP_OPEN_ON_FOCUS_LOST,
			)

		else:
			utils.log("no profiles detected")

	def show_product_lookup_menu(self):
		sublime.active_window().show_quick_panel(
			self.PRODUCT_LOOKUP_MENU_ITEMS,
			lambda x: self.process_product_lookup_menu(self.PRODUCT_LOOKUP_MENU_ITEMS[x]) if x != -1 else None,
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

	def show_cms_page_menu(self, index):
		if index == -1:
			return False

		menu_items = []

		for item in self.CMS_PAGE_MENU_ITEMS:
			if item == "{toggle} page":
				item = item.format(toggle = check_active(self.API_RESPONSE_ITEMS[index]["active"]))

			menu_items.append(item)

		sublime.active_window().show_quick_panel(
			menu_items,
			lambda x: self.process_cms_page_menu(x, index),
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

	def show_cms_block_menu(self, index):
		if index == -1:
			return False

		menu_items = []

		for item in self.CMS_BLOCK_MENU_ITEMS:
			if item == "{toggle} block":
				item = item.format(toggle = check_active(self.API_RESPONSE_ITEMS[index]["active"]))

			menu_items.append(item)

		sublime.active_window().show_quick_panel(
			menu_items,
			lambda x: self.process_cms_block_menu(x, index),
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

	def show_category_menu(self, category):
		on_done = lambda x: self.process_category_menu(self.CATEGORY_MENU_ITEMS[x], category) if x != -1 else None

		sublime.active_window().show_quick_panel(
			self.CATEGORY_MENU_ITEMS,
			on_done,
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

	def show_product_menu(self, product):
		on_done = lambda x: self.process_product_menu(self.PRODUCT_MENU_ITEMS[x], product) if x != -1 else None

		sublime.active_window().show_quick_panel(
			self.PRODUCT_MENU_ITEMS,
			on_done,
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

	def show_order_menu(self, order):
		on_done = lambda x: self.process_order_menu(self.ORDER_MENU_ITEMS[x], order) if x != -1 else None

		sublime.active_window().show_quick_panel(
			self.ORDER_MENU_ITEMS,
			on_done,
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

	def process_cms_page_menu(self, index, page_index):
		if index == -1:
			return False

		action = self.CMS_PAGE_MENU_ITEMS[index]
		page   = self.API_RESPONSE_ITEMS[page_index]

		if action == "Insert page contents":
			self.insert_cms_resource("cmsPage", page)

		elif action == "View in browser":
			utils.open_url(page["site_url"])

		elif action == "View in Magento":
			utils.open_url(page["admin_url"])

		elif action == "Edit title...":
			on_done = lambda title: update_cms_resource("cmsPage", page["id"], {"title": title}) if title.strip() != "" else None
			sublime.active_window().show_input_panel("Title:", page["title"], on_done, None, None).run_command("select_all")

		elif action == "Edit identifier...":
			on_done = lambda identifier: update_cms_resource("cmsPage", page["id"], {"identifier": identifier}) if identifier.strip() != "" else None
			sublime.active_window().show_input_panel("Identifier:", page["identifier"], on_done, None, None).run_command("select_all")

		elif action == "Insert identifier":
			insert_text(page["identifier"])

		elif action == "{toggle} page":
			update_cms_resource("cmsPage", page["id"], {"active": (not page["active"])})

		elif action == "Debug info":
			url = "cmsPage/{}".format(page["id"])
			response = api.request("GET", url)
			utils.dump_as_json(response)

	def process_cms_block_menu(self, index, block_index):
		if index == -1:
			return False

		action = self.CMS_BLOCK_MENU_ITEMS[index]
		block  = self.API_RESPONSE_ITEMS[block_index]

		if action == "Insert block contents":
			self.insert_cms_resource("cmsBlock", block)

		elif action == "View in Magento":
			utils.open_url(block["admin_url"])

		elif action == "Edit title...":
			on_done = lambda title: update_cms_resource("cmsBlock", block["id"], {"title": title}) if title.strip() != "" else None
			sublime.active_window().show_input_panel("Title:", block["title"], on_done, None, None).run_command("select_all")

		elif action == "Edit identifier...":
			on_done = lambda identifier: update_cms_resource("cmsBlock", block["id"], {"identifier": identifier}) if identifier.strip() != "" else None
			sublime.active_window().show_input_panel("Identifier:", block["identifier"], on_done, None, None).run_command("select_all")

		elif action == "Insert identifier":
			insert_text(block["identifier"])

		elif action == "{toggle} block":
			update_cms_resource("cmsBlock", block["id"], {"active": (not block["active"])})

		elif action == "Debug info":
			url = "cmsBlock/{}".format(block["id"])
			response = api.request("GET", url)
			utils.dump_as_json(response)

	def process_category_menu(self, action, category):
		if action == "Insert URL key":
			if "url_path" in category:
				insert_text(category["url_path"])
			else:
				utils.log('category has no "url_path" property')

		elif action == "View in browser":
			utils.open_url(category["site_url"])

		elif action == "View in Magento":
			utils.open_url(category["admin_url"])

		elif action == "Debug info":
			response = api.request("GET", "categories/{}".format(category["id"]))
			utils.dump_as_json(response)

	def process_product_menu(self, action, product):
		if action == "View in browser":
			utils.open_url(product["site_url"])

		elif action == "View in Magento":
			utils.open_url(product["admin_url"])

		elif action == "Debug info":
			get_product_by_sku(product["sku"])

	def process_product_lookup_menu(self, action):
		if action == "By SKU":
			caption = "SKU"
			on_done = lambda x: get_product_by_sku(x) if x.strip() != "" else None

		elif action == "By ID":
			caption = "ID"
			on_done = lambda x: get_product_by_id(x) if x.strip() != "" else None

		sublime.active_window().show_input_panel(caption, "", on_done, None, None)

	def process_order_menu(self, action, order):
		if action == "View in Magento":
			utils.open_url(order["admin_url"])

		elif action == "Debug info":
			response = api.request("GET", "orders/{}".format(order["entity_id"]))
			utils.dump_as_json(response)

	def insert_cms_resource(self, resource_type, resource):
		response = api.request("GET", "{}/{}".format(resource_type, resource["id"]))

		if "content" in response:
			temp_folder = get_temp_folder()

			if not os.path.exists(temp_folder):
				os.makedirs(temp_folder)

			file_name = generate_file_name(resource_type, resource)

			temp_file_path = os.path.join(temp_folder, file_name + ".html")

			with open(temp_file_path, "w", encoding = "utf-8", newline = "\n") as f:
				f.write(response["content"])

			sublime.active_window().open_file(temp_file_path)

			# Update sheet list
			sheet_id = sublime.active_window().active_sheet().id()

			self.SHEET_LIST[sheet_id] = {
				"type"       : resource_type,
				"id"         : resource["id"],
				"identifier" : resource["identifier"],
			}

		else:
			raise Exception("Error fetching content")


class Magento2StuffEventListener(sublime_plugin.EventListener):
	menu_is_open = False

	def on_text_command(self, window, command_name, args):
		if command_name == "magento2_stuff":
			self.menu_is_open = True

		elif command_name in utils.get_setting("exit_commands") and self.menu_is_open:
			window.window().run_command("hide_overlay")
			self.menu_is_open = False

	def on_pre_save(self, view):
		sheet_info = get_current_sheet_info(False)

		if sheet_info:
			url = "{}/{}".format(sheet_info["type"], sheet_info["id"])

			sheet_content = get_current_sheet_content()

			request_body = {}

			key = "page" if sheet_info["type"] == "cmsPage" else "block"

			request_body[key] = {
				"content": sheet_content
			}

			api.request("PUT", url, request_body = request_body)

	# To-do: implement deleting files on close, if desired
	def on_pre_close(self, view):
		sheet_id = sublime.active_window().active_sheet().id()

		if sheet_id in Magento2StuffCommand.SHEET_LIST:
			# If a sheet is closed then re-opened (e.g. via ctrl+shift+t), it is NOT
			# re-assigned the same ID, but instead assigned a new one.
			#
			# It is therefore not strictly necessary to maintain SHEET_LIST by
			# removing "old" IDs, but doing so makes it easier to debug.
			del Magento2StuffCommand.SHEET_LIST[sheet_id]


# Misc. functions
def update_cms_resource(endpoint, resource_id, properties):
	url = "{}/{}".format(endpoint, resource_id)

	request_body = {}

	resource_type = "page" if endpoint == "cmsPage" else "block"

	request_body[resource_type] = {}

	for key in properties:
		request_body[resource_type][key] = properties[key]

	api.request("PUT", url, request_body = request_body)

def get_product_by_sku(sku, dump = True):
	response = api.request("GET", "products/{}".format(sku))

	response["admin_url"] = get_admin_url("product", response["id"])

	if not dump:
		return response

	utils.dump_as_json(response)

def get_product_by_id(entity_id):
	pass

def go_to_admin_url():
	sheet_info = get_current_sheet_info()

	if sheet_info:
		admin_url = get_admin_url(sheet_info["type"], sheet_info["id"])
		utils.open_url(admin_url)

def go_to_site_url():
	sheet_info = get_current_sheet_info()

	if sheet_info:
		if sheet_info["type"] == "cmsPage":
			site_url = get_site_url(sheet_info["identifier"])
			utils.open_url(site_url)

		# CMS blocks don't have a front-end URL, so just return the admin link instead
		elif sheet_info["type"] == "cmsBlock":
			go_to_admin_url()

def backup_current_sheet():
	sheet_info = get_current_sheet_info()

	if sheet_info:
		backup_dir = create_backup_folder_name(sheet_info["identifier"])

		if backup_dir:
			if not os.path.exists(backup_dir):
				utils.log("creating folder: " + backup_dir)
				os.makedirs(backup_dir)

			file_name = time.strftime("%Y-%m-%d %H.%M.%S") + ".html"
			file_path = os.path.join(backup_dir, file_name)

			sheet_content = get_current_sheet_content()

			with open(file_path, "w", encoding = "utf-8", newline = "\n") as f:
				utils.log("creating file: " + file_path)
				f.write(sheet_content)

			if utils.get_setting("open_folder_after_backup"):
				sublime.active_window().run_command("open_dir", {
					"dir": backup_dir
				})

def show_backup_files_list_menu():
	sheet_info = get_current_sheet_info()

	if sheet_info:
		backup_dir = create_backup_folder_name(sheet_info["identifier"])

		if not os.path.exists(backup_dir):
			return utils.log("backup folder not found: " + backup_dir)

		backup_list_menu_items = []
		file_paths = []

		for file_name in os.listdir(backup_dir):
			file_path = os.path.join(backup_dir, file_name)

			# Backup dir may contain directories
			if os.path.isfile(file_path):
				mtime = os.path.getmtime(file_path)
				mtime_str = datetime.utcfromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

				backup_list_menu_items.append([file_name, format_datetime_str(mtime_str)])
				file_paths.append(file_path)

		if not file_paths:
			return utils.log("backup directory is empty for current file")

		backup_list_menu_items.sort(key = lambda item: item[0], reverse = True)
		file_paths.sort(reverse = True)

		sublime.active_window().show_quick_panel(
			backup_list_menu_items,
			lambda index: diff_file(index, file_paths),
			sublime.KEEP_OPEN_ON_FOCUS_LOST,
		)

def diff_file(index, file_paths):
	if index == -1:
		return False

	# Ensure WinMerge binary exists before continuing
	winmerge_path = utils.get_setting("winmerge_path")

	if not winmerge_path:
		return utils.log('settings value "winmerge_path" required')

	if not os.path.isfile(winmerge_path):
		return utils.log("WinMerge path not found: " + winmerge_path)

	this_file = get_current_file_name()

	if this_file == None:
		return utils.log("current sheet is not a saved file")

	target = lambda: subprocess.check_output([
		winmerge_path,
		this_file,
		file_paths[index],
	])

	thread = threading.Thread(target = target)
	thread.start()

def create_backup_folder_name(identifier):
	base_backup_dir = utils.get_setting("backup_folder_path")

	if not base_backup_dir:
		utils.log('settings value "backup_folder_path" required')
		return False

	# CMS resource identifier is used as folder name
	subfolder_name = urllib.parse.quote_plus(identifier)

	backup_dir = os.path.join(base_backup_dir, subfolder_name)

	return backup_dir

def get_admin_url(resource_type, resource_id):
	if resource_type == "cmsPage":
		return M2_URLS.ADMIN_URL_CMS_PAGE.format(resource_id)

	elif resource_type == "cmsBlock":
		return M2_URLS.ADMIN_URL_CMS_BLOCK.format(resource_id)

	elif resource_type == "category":
		return M2_URLS.ADMIN_URL_CATEGORY.format(resource_id)

	elif resource_type == "product":
		return M2_URLS.ADMIN_URL_PRODUCT.format(resource_id)

	elif resource_type == "order":
		return M2_URLS.ADMIN_URL_ORDER.format(resource_id)

	utils.log("unknown resource type: " + resource_type)

def get_site_url(identifier):
	return M2_URLS.BASE_URL + identifier

def get_temp_folder():
	return os.path.join(tempfile.gettempdir(), utils.get_setting("temp_folder_name"))

def get_current_file_name():
	return sublime.active_window().active_view().file_name()

def get_current_sheet_info(warn = True):
	sheet_id = sublime.active_window().active_sheet().id()

	if sheet_id in Magento2StuffCommand.SHEET_LIST:
		return Magento2StuffCommand.SHEET_LIST[sheet_id]

	if warn:
		utils.log("sheet ID not in sheet list")

	return None

def get_current_sheet_content():
	current_sheet = sublime.active_window().active_sheet().view()
	return current_sheet.substr(sublime.Region(0, current_sheet.size()))

def generate_file_name(resource_type, resource):
	return "{}_{}_{}_{}_{}".format(
		resource_type,
		resource["id"],
		urllib.parse.quote_plus(resource["identifier"]),
		str(time.time()).replace(".", ""),
		uuid.uuid4(),
	)

def insert_text(text):
	sublime.active_window().run_command("insert_snippet", {
		"contents": text
	})

def format_datetime_str(datetime_str):
	now     = datetime.now()
	updated = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
	delta   = now - updated

	# Less than a day, e.g. "18 hours, 24 minutes, 36 seconds"
	if delta.days < 1:
		hours   = math.floor(delta.seconds / 60 / 60)
		minutes = math.floor(delta.seconds / 60) % 60
		seconds = delta.seconds % 60

		return "{} {}, {} {}, {} {}".format(
			hours,
			check_plural(hours, "hour"),
			minutes,
			check_plural(minutes, "minute"),
			seconds,
			check_plural(seconds, "second"),
		)

	# Less than a year, e.g. "1 day ago"
	if delta.days < 365:
		return "{} {} ago".format(
			delta.days,
			check_plural(delta.days, "day"),
		)

	# "More than a year ago"
	years = delta.days // 365

	return "More than {} {} ago".format(
		years,
		check_plural(years, "year"),
	)

def check_active(active):
	if active:
		return "Disable"

	return "Enable"

def check_plural(num, text):
	if num == 1:
		return text

	return text + "s"