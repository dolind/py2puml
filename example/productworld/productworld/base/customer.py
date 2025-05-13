from typing import List

from productworld.base.base import Order,fancyFunc, NewOrder


class Customer:
    def __init__(self, customer_id, name):
        self.customer_id = customer_id
        self.name = name
        self.orders = []
        self.newestOrder :NewOrder = NewOrder()

    def add_order(self, order: Order):
        self.orders.append(order)
        self.orders.append(NewOrder())
        fancyFunc(order)

    def get_total_spent(self)-> int:
        return sum(order.calculate_total() for order in self.orders)
        

