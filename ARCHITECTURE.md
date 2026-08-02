{% extends "base.html" %}
{% block title %}{% if product %}ویرایش{% else %}افزودن{% endif %} کالا{% endblock %}
{% block page_title %}<strong>{% if product %}ویرایش کالا{% else %}کالای جدید{% endif %}</strong>{% endblock %}
{% block content %}
<div class="card" style="max-width:600px;">
    <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <div class="form-row">
            <div class="form-group">
                <label>کد کالا *</label>
                <input type="text" name="code" class="form-control" required value="{{ product.code if product else '' }}">
            </div>
            <div class="form-group">
                <label>نام کالا *</label>
                <input type="text" name="name" class="form-control" required value="{{ product.name if product else '' }}">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>واحد اندازه‌گیری</label>
                <input type="text" name="unit" class="form-control" value="{{ product.unit if product else 'عدد' }}">
            </div>
            <div class="form-group">
                <label>موجودی فعلی</label>
                <input type="number" step="0.01" name="stock_qty" class="form-control" value="{{ product.stock_qty if product else 0 }}">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>قیمت خرید</label>
                <input type="number" step="1" name="buy_price" class="form-control" value="{{ product.buy_price if product else 0 }}">
            </div>
            <div class="form-group">
                <label>قیمت فروش</label>
                <input type="number" step="1" name="sell_price" class="form-control" value="{{ product.sell_price if product else 0 }}">
            </div>
        </div>
        <button type="submit" class="btn btn-primary">ذخیره</button>
        <a href="{{ url_for('products') }}" class="btn btn-secondary">انصراف</a>
    </form>
</div>
{% endblock %}
