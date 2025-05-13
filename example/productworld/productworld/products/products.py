from productworld.base.base import Product

from productworld.base.base import funkyFunc
     
class PhysicalProduct(Product):
    def __init__(self, product_id, name, price):
        super().__init__(product_id, name)
        self.price = price

    def get_price(self):
        return self.price

class DigitalProduct(Product):
    def __init__(self, product_id, name, price, discount):
        super().__init__(product_id, name)
        self.price = price
        self.discount = discount
        funkyFunc()

    def get_price(self)->int:
        return self.price * (1 - self.discount) 
        
class Productfactory():
 def create_product(self,pid:str)->PhysicalProduct|DigitalProduct:
   return PhysicalProduct()
   
def create_product(self,pid:str)->PhysicalProduct|DigitalProduct:
  return PhysicalProduct()
