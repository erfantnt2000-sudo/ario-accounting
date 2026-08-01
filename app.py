{% extends "base.html" %}
{% block title %}گزارش سرویس{% endblock %}
{% block page_title %}<strong>گزارش سرویس</strong>{% endblock %}
{% block content %}
<div class="card">
  <h2>{{ visit.building_name or '' }} — {{ visit.elev_code }}</h2>
  <p style="color:var(--muted);font-size:0.9rem;">
    {% if visit.customer_name %}کارفرما: {{ visit.customer_name }} · {% endif %}
    {% if visit.customer_phone %}{{ visit.customer_phone }}{% endif %}
    {% if visit.building_address %}<br>📍 {{ visit.building_address }}{% endif %}
  </p>
</div>
<form method="post" class="card">
  <h3>چک‌لیست استاندارد سرویس</h3>
  <p style="font-size:0.85rem;color:var(--muted);margin-bottom:12px;">موارد بررسی‌شده را تیک بزنید.</p>
  {% for key, label in checklist %}
  <label class="chk-row">
    <input type="checkbox" name="chk_{{ key }}" value="1" checked>
    <span>{{ label }}</span>
  </label>
  {% endfor %}

  <div class="form-group" style="margin-top:16px;">
    <label>گزارش کار / توضیحات</label>
    <textarea name="report_text" class="form-control" rows="3" placeholder="شرح کارهای انجام‌شده..."></textarea>
  </div>
  <div class="form-group">
    <label>یادداشت عکس / مستندات</label>
    <input name="photo_note" class="form-control" placeholder="مثلاً: عکس موتور و درب گرفته شد">
  </div>
  <div class="form-group">
    <label>امضای کارفرما / مدیر ساختمان</label>
    <input name="customer_sign" class="form-control" placeholder="نام امضاکننده" required>
  </div>
  <button type="submit" class="btn btn-success" style="width:100%;min-height:48px;">✓ ثبت انجام سرویس</button>
  <a href="{{ url_for('tech_home') }}" class="btn btn-secondary" style="width:100%;margin-top:8px;">انصراف</a>
</form>
{% endblock %}
