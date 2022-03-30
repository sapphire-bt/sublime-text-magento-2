import json
import os
import sublime
import tempfile
import threading
import time
import uuid
import webbrowser

class Magento2Utils():
	SETTINGS_NAME = "Magento2Stuff.sublime-settings"

	@staticmethod
	def get_current_profile():
		profiles = Magento2Utils.get_setting("profiles")

		if not profiles:
			raise Exception("No profiles found")

		index = Magento2Utils.get_setting("current_profile")

		if index == None:
			index = 0

		return profiles[index]

	@staticmethod
	def get_temp_folder():
		return os.path.join(tempfile.gettempdir(), Magento2Utils.get_setting("temp_folder_name"))

	@staticmethod
	def get_setting(name):
		return sublime.load_settings(Magento2Utils.SETTINGS_NAME).get(name)

	@staticmethod
	def set_setting(name, value):
		sublime.load_settings(Magento2Utils.SETTINGS_NAME).set(name, value)
		sublime.save_settings(Magento2Utils.SETTINGS_NAME)

	@staticmethod
	def open_url(url):
		browser_path = Magento2Utils.get_setting("preferred_browser")

		if browser_path and os.path.isfile(browser_path):
			browser_path = browser_path.replace("\\", "/")

			target = lambda: webbrowser.get(browser_path + " %s").open(url)

			thread = threading.Thread(target = target)
			thread.start()

		else:
			webbrowser.open(url)

	@staticmethod
	def log(message):
		message = "[{}] Magento2Stuff: {}".format(time.strftime("%Y-%m-%d %H:%M:%S"), message.strip())
		sublime.status_message(message)
		print(message)

	@staticmethod
	def dump_as_json(dictionary):
		temp_folder = Magento2Utils.get_temp_folder()

		if not os.path.exists(temp_folder):
			os.makedirs(temp_folder)

		file_name = "{}_{}".format(str(time.time()).replace(".", ""), uuid.uuid4())
		temp_file_path = os.path.join(temp_folder, file_name + ".json")

		with open(temp_file_path, "w", encoding = "utf-8", newline = "\n") as f:
			f.write(json.dumps(dictionary, indent = "\t", separators = (",", ": ")))

		sublime.active_window().open_file(temp_file_path)