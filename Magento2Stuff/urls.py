from Magento2Stuff.utils import Magento2Utils as utils

class Magento2StuffSettings():
	@property
	def BASE_URL(self):
		return utils.get_current_profile()["base_url"]

	@property
	def API_URL(self):
		return self.BASE_URL + "index.php/rest/all/V1/"

	@property
	def CATEGORY_ID_URL(self):
		return self.BASE_URL + "catalog/category/view/id/{}/"

	@property
	def CATALOG_URL(self):
		return self.BASE_URL + "media/catalog/product" # API response includes leading slash for images...

	@property
	def ADMIN_URL_CMS_PAGE(self):
		return self.BASE_URL + "admin/cms_page/edit/page_id/{}/"

	@property
	def ADMIN_URL_CMS_BLOCK(self):
		return self.BASE_URL + "cms/block/edit/block_id/{}/"

	@property
	def ADMIN_URL_CATEGORY(self):
		return self.BASE_URL + "catalog/category/edit/id/{}/"

	@property
	def ADMIN_URL_PRODUCT(self):
		return self.BASE_URL + "catalog/product/edit/id/{}/"

	@property
	def ADMIN_URL_ORDER(self):
		return self.BASE_URL + "sales/order/view/order_id/{}/"