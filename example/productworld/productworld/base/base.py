from abc import ABC, abstractmethod

class Product(ABC):
    def __init__(self, product_id, name):
        self.product_id = product_id
        self.name = name

    @abstractmethod
    def get_price(self):
        pass


class NewOrder:
    def __init__(self, order_id, product: Product, quantity):
        self.order_id = order_id
        self.product:Product = product
        self.quantity = quantity

    def calculate_total(self, product:Product)->int:
        return self.product.price * self.quantity

class Order:
    def __init__(self, order_id, product:Product, quantity):
        self.order_id = order_id
        self.product = Product()
        self.quantity = quantity

    def calculate_total(self)->int:
        return self.product.price * self.quantity

        
def fancyFunc(order: Order):
  return 42
  
def funkyFunc():
 return 42
