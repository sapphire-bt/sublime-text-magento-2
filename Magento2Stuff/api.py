import base64
import json
import urllib
import uuid

from collections.abc import MutableMapping

from Magento2Stuff.urls import Magento2StuffSettings
from Magento2Stuff.utils import Magento2Utils as utils

M2_URLS = Magento2StuffSettings()

class MagentoAPI():
	@staticmethod
	def request(request_type, endpoint, search_criteria = None, fields = None, request_body = None):
		api_key = utils.get_setting("api_key")

		url = M2_URLS.API_URL + endpoint

		profile = utils.get_current_profile()

		if request_type == "GET":
			# Convert any search/field parameters to a URL query string
			params = {}

			if search_criteria != None:
				if search_criteria == 0:
					params["search_criteria"] = 0

				else:
					params = MagentoAPI.flatten({"search_criteria": search_criteria})

			if fields:
				params["fields"] = MagentoAPI.flatten_fields(fields)

			# Always include cache breaker
			params[str(uuid.uuid4())] = 1

			url += "?" + urllib.parse.urlencode(params)

			req = urllib.request.Request(url = url, method = request_type)

		elif request_type == "PUT":
			data = json.dumps(request_body).encode()

			req = urllib.request.Request(url = url, data = data, method = request_type)

		req.add_header("Accept",        "application/json")
		req.add_header("Authorization", "Bearer " + api_key)
		req.add_header("Content-Type",  "application/json;charset=\"utf-8\"")

		response = urllib.request.urlopen(req).read().decode()

		return json.loads(response)

	# Python implementation of PHP's http_build_query function - https://stackoverflow.com/a/65617512/7290573
	@staticmethod
	def flatten(dictionary, parent_key = False, separator = "[", separator_suffix = "]"):
		items = []

		for key, value in dictionary.items():
			new_key = str(parent_key) + separator + key + separator_suffix if parent_key else key
			if isinstance(value, MutableMapping):
				items.extend(MagentoAPI.flatten(value, new_key, separator, separator_suffix).items())
			elif isinstance(value, list) or isinstance(value, tuple):
				for k, v in enumerate(value):
					items.extend(MagentoAPI.flatten({str(k): v}, new_key, separator, separator_suffix).items())
			else:
				items.append((new_key, value))

		return dict(items)

	@staticmethod
	def flatten_fields(fields):
		items = []

		if isinstance(fields, dict):
			fields = [fields]

		for field in fields:
			if isinstance(field, dict):
				for key in field:
					flat = key + "[" + MagentoAPI.flatten_fields(field[key]) + "]"
					items.append(flat)
			else:
				items.append(field)

		return ",".join(items)