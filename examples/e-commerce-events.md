Account Created
- Description: When the user successfully creates their account.
- Properties:
  * account creation date; YYYY-MM-DD; Date when user created their account.
  * account type; email, facebook, twitter; Type of login used to create account.

Search
- Description: Triggered after 3 characters have been entered.
- Properties:
  * number of results; 1, 10, 15; The number of results returned.
  * keywords; shoes, jeans; The keywords used in the search.

Product Clicked
- Description: When a user clicks on a product.
- Properties:
- rank; 1, 2, 3; The rank of the product in the search results.
  * product id; 1234, 483771, 833194; The internal identifier for the product.
  * product name; tie dye shirt, shorts; The name of the product.
  * price; 15.99, 4; The price of the product.

Product Details Viewed
- Description: When a user views the details of a product.
- Properties:
  * page source; discover feed, wishlist; Where the user came from to view the product details.

Product Added
- Description: When a user adds a product to their cart. 
- Properties:
  * cart id; $07ab0b4e-0a9f-4399-9a7a-5b2ff8add32d; Unique identifier for the cart.
  * quantity; 1, 2, 3; The quantity of the product added. 

Checkout Started
- Description: When a user starts the checkout process. 
- Properties:
  * cart total; size 2, 6; The total value of the items in the cart. 
  * coupon code; BOGO2021, 50%off; The coupon code applied to the order. 

Product Removed
- Description: When a user removes a product from their cart. 

Shipping Info Added
- Description: When a user adds their shipping information. 
- Properties:
  * shipping method; express, standard; The shipping method selected by the user. 

Payment Info Added
- Description: When a user adds their payment information. 
- Properties:
  * payment method; credit, apple pay, paypal; The payment method selected by the user. 

Order Completed
- Description: When a user successfully completes an order.
- Properties:
  * order total; 110.99; The total amount of the order, including tax. 
  * revenue; 99.99; The amount of revenue from the order.
  * tax; 4.55; The amount of tax for the order. 

Order Edited
- Description: When a user makes changes to their order. 
- Properties:
  * fields modified; The fields that were modified in the order.


Order Cancelled
- Description: When an order is cancelled before the item is received.
- Properties:
  * reason; missed delivery, out-of-stock, backorder; The reason for the cancellation.

Error Triggered
- Description: When an error is encountered anywhere in the browse or checkout flow.
- Properties:
  * error code; The exact error code.