import random, uuid, requests
from datetime import datetime, timedelta

URL = "http://localhost:8000/track"
PRODUCTS = [("P101","Wireless Earbuds","Electronics",49.99),("P102","Smart Watch","Electronics",129.0),
 ("P103","Bluetooth Speaker","Electronics",39.5),("P104","Laptop Backpack","Fashion",34.9),
 ("P105","Running Shoes","Fashion",79.0),("P106","Denim Jacket","Fashion",59.0),
 ("P107","Coffee Maker","Home",89.0),("P108","Desk Lamp","Home",24.99),
 ("P109","Throw Blanket","Home",29.0),("P110","Data Engineering Handbook","Books",42.0),
 ("P111","SQL Cookbook","Books",28.0),("P112","Notebook Set","Books",12.5)]
SOURCES  = ["organic", "paid", "email", "social", "direct"]
SRC_W    = [35, 25, 15, 15, 10]
SRC_CONV = {"organic": 1.0, "paid": 0.8, "email": 1.6, "social": 0.6, "direct": 1.2}
TERMS    = ["shoes", "lamp", "earbuds", "book", "jacket", "sql", "watch", "laptop", "phone", "tv", "headphones"]
HOUR_W   = [1,1,1,1,1,2,3,5,6,6,6,7,8,7,6,6,7,8,10,11,10,8,5,3]

random.seed(42)
users = [f"u{i}" for i in range(1, 801)]
devices = {u: random.choices(["mobile", "desktop", "tablet"], [55, 38, 7])[0] for u in users}
start = datetime(2026, 10, 12)
batch, total = [], 0

def flush():
    global batch, total
    if batch:
        requests.post(URL, json=batch, timeout=60).raise_for_status()
        total += len(batch); batch = []

def run_session(uid, day):
    device = devices[uid]
    src = random.choices(SOURCES, SRC_W)[0]
    t = start + timedelta(days=day, hours=random.choices(range(24), HOUR_W)[0],
                          minutes=random.randint(0, 59), seconds=random.randint(0, 59))
    sid = str(uuid.uuid4())

    def ev(typ, page, btn=None, feat=None, **props):
        nonlocal t
        t += timedelta(seconds=random.randint(2, 40))
        batch.append(dict(event_id=str(uuid.uuid4()), user_id=uid, session_id=sid,
                          event_ts=t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                          interaction_type=typ, page_name=page, button_name=btn, feature_name=feat,
                          device=device, app_version="1.0.0", properties={"traffic_source": src, **props}))

    ev("page_view", "/home")
    if random.random() < 0.45:                                   # search path
        term = random.choice(TERMS)
        pool = [p for p in PRODUCTS if term in (p[1] + " " + p[2]).lower()]
        ev("click", "/home", "search_submit", "search")
        ev("search", "/home", feat="search", search_term=term, results_count=len(pool))
        ev("page_view", "/products")
    else:                                                        # category path
        cat = random.choice(["Electronics", "Fashion", "Home", "Books"])
        pool = [p for p in PRODUCTS if p[2] == cat]
        ev("click", "/home", "category_tile", "catalog_filter")
        ev("filter", "/products", feat="catalog_filter", filter_type="category",
           filter_value=cat, results_count=len(pool))
        ev("page_view", "/products")
    if not pool:
        return                                                   # zero results -> bounce

    cart = {}
    for pid, name, cat, price in random.sample(pool, min(len(pool), random.randint(1, 4))):
        base = dict(product_id=pid, product_name=name, category=cat, price=price)
        ev("click", "/products", "view_product", "product_detail", product_id=pid)
        ev("product_view", f"/product/{pid}", feat="product_detail", **base)
        if random.random() < 0.08:
            ev("wishlist", f"/product/{pid}", feat="wishlist", action="added", **base)
        p_add = 0.35 * (1.2 if device == "desktop" else 0.9) * (1.3 if price < 40 else 0.8 if price > 75 else 1)
        if random.random() < p_add:
            cart[pid] = cart.get(pid, 0) + 1
            cv = round(sum(next(x[3] for x in PRODUCTS if x[0] == k) * q for k, q in cart.items()), 2)
            ev("click", f"/product/{pid}", "add_to_cart", "cart", product_id=pid)
            ev("add_to_cart", f"/product/{pid}", feat="cart", quantity=1, cart_value=cv, **base)
    if not cart:
        return

    items = [dict(product_id=k, product_name=next(x[1] for x in PRODUCTS if x[0] == k),
                  category=next(x[2] for x in PRODUCTS if x[0] == k),
                  price=next(x[3] for x in PRODUCTS if x[0] == k), quantity=q) for k, q in cart.items()]
    sub = sum(i["price"] * i["quantity"] for i in items)
    n_items = sum(cart.values())
    ev("page_view", "/cart")
    coupon = None
    if random.random() < 0.30:
        valid = random.random() < 0.75
        ev("click", "/cart", "apply_coupon", "promotions")
        ev("coupon_apply", "/cart", feat="promotions", coupon_code="SAVE10" if valid else "FREESHIP", valid=valid)
        coupon = "SAVE10" if valid else None
    if random.random() > 0.55 * (1.1 if coupon else 1):
        return                                                   # abandoned in cart
    ev("click", "/cart", "checkout", "checkout")
    ev("checkout_start", "/cart", feat="checkout", cart_value=round(sub, 2), item_count=n_items,
       coupon_code=coupon, items=items)
    ev("page_view", "/checkout")
    if random.random() > min(0.9, 0.62 * SRC_CONV[src] * (1.2 if coupon else 1)):
        return                                                   # abandoned at checkout
    disc = sub * 0.10 if coupon else 0
    ship = 0 if sub - disc >= 50 else 5
    ev("click", "/checkout", "place_order", "checkout")
    ev("purchase", "/checkout", feat="checkout", order_id="ORD" + uuid.uuid4().hex[:6].upper(),
       order_value=round(sub - disc + ship, 2), subtotal=round(sub, 2), discount=round(disc, 2),
       shipping=ship, coupon_code=coupon, item_count=n_items, items=items,
       payment_method=random.choices(["card", "cash_on_delivery", "wallet"], [60, 25, 15])[0])
    ev("page_view", "/order-confirmation")

for day in range(30):
    d = start + timedelta(days=day)
    n = int(random.gauss(260, 35) * (1.25 if d.weekday() >= 5 else 1) * (1 + day * 0.012))
    for _ in range(n):
        run_session(random.choice(users), day)
        if len(batch) > 3000:
            flush()
flush()
print("events sent:", total)