---
layout: page
title: 언제 꺼내는가
icon: fas fa-compass
order: 5
---

<!--
  목적축(purpose) 인덱스.
  기술명을 몰라도 "지금 겪는 상황"으로 글을 찾을 수 있게 하는 페이지다.
  프론트매터의 커스텀 키 `purpose` 를 Liquid 로 묶는다 — 플러그인을 쓰지 않는다.

  축 목록은 아래 AXES 한 줄이 전부다. `축:라벨` 쌍이라 한쪽만 고칠 수 없다.
  이 목록은 tools/tag_vocabulary.json 의 purpose 와 같아야 하며,
  어긋나면 validate_tags.py 가 FAIL 로 잡는다. 손으로 맞추기를 기대하지 않는다.
-->

{% assign AXES = "bypass:막혔을 때,perf:느릴 때,cost:비용이 나갈 때,verify:맞는지 의심될 때,automate:반복이 많을 때,resilience:장애가 날 때,structure:설계를 정할 때,survey:종류를 고를 때,ops:쌓인 걸 치울 때,retro:돌아볼 때" | split: "," %}

{%- assign known = "|" -%}
{%- for pair in AXES -%}
  {%- assign kv = pair | split: ":" -%}
  {%- assign known = known | append: kv[0] | append: "|" -%}
{%- endfor -%}
{%- assign tagged = site.posts | where_exp: "p", "p.purpose" -%}

> 기술 이름이 아니라 **그때 떠오르는 상황**으로 찾는 색인이다. 총 {{ tagged.size }}편.
{: .prompt-tip }

{% for pair in AXES %}
{%- assign kv = pair | split: ":" -%}
{%- assign axis = kv[0] -%}
{%- assign posts = site.posts | where: "purpose", axis -%}
<h2 id="{{ axis }}">{{ kv[1] }} <small><code>{{ axis }}</code> · {{ posts.size }}편</small></h2>
{%- if posts.size == 0 %}
<p><em>아직 없다.</em></p>
{%- else %}
<ul>
{%- for post in posts %}
  <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a>{% if post.domain %} <small class="text-muted">— {{ post.domain }}</small>{% endif %}</li>
{%- endfor %}
</ul>
{%- endif %}
{% endfor %}

{%- assign orphan_count = 0 -%}
{%- for post in tagged -%}
  {%- assign probe = "|" | append: post.purpose | append: "|" -%}
  {%- unless known contains probe -%}{%- assign orphan_count = orphan_count | plus: 1 -%}{%- endunless -%}
{%- endfor -%}

{% if orphan_count > 0 %}
## 축 밖에 있는 글

> 아래 글은 위 목록에 없는 `purpose` 값을 써서 어느 항목에도 안 잡힌다. 축 목록이나 글의 값 중 하나가 틀렸다는 뜻이다.
{: .prompt-warning }

<ul>
{%- for post in tagged -%}
{%- assign probe = "|" | append: post.purpose | append: "|" -%}
{%- unless known contains probe %}
  <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a> — <code>{{ post.purpose }}</code></li>
{%- endunless -%}
{%- endfor %}
</ul>
{% endif %}
