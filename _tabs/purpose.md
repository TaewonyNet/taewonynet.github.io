---
layout: page
title: 언제 꺼내는가
icon: fas fa-compass
order: 4
---

<!--
  목적축(purpose) 인덱스.
  기술명을 몰라도 "지금 겪는 상황"으로 글을 찾을 수 있게 하는 페이지다.
  프론트매터의 커스텀 키 `purpose` 를 Liquid 로 묶는다 — 플러그인을 쓰지 않는다.
  어휘는 Blog/scripts/tag_vocabulary.json 과 같아야 한다.
-->

{% assign axes = "bypass,perf,cost,verify,automate,resilience,structure,survey,ops,retro" | split: "," %}
{% assign labels = "막혔을 때,느릴 때,비용이 나갈 때,맞는지 의심될 때,반복이 많을 때,장애가 날 때,설계를 정할 때,종류를 고를 때,쌓인 걸 치울 때,돌아볼 때" | split: "," %}

> 기술 이름이 아니라 **그때 떠오르는 상황**으로 찾는 색인이다.
{: .prompt-tip }

{% for axis in axes %}
  {% assign posts = site.posts | where: "purpose", axis %}
  {% if posts.size > 0 %}
<h2 id="{{ axis }}">{{ labels[forloop.index0] }} <small><code>{{ axis }}</code> · {{ posts.size }}편</small></h2>

<ul>
  {% for post in posts %}
  <li>
    <a href="{{ post.url | relative_url }}">{{ post.title }}</a>
    {% if post.domain %}<small class="text-muted">— {{ post.domain }}</small>{% endif %}
  </li>
  {% endfor %}
</ul>
  {% endif %}
{% endfor %}
