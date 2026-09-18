#!/usr/bin/env ruby
#
# 글이 몇 편 없는 태그/카테고리 페이지는 **색인을 요청하지 않는다** — 2026-09-18.
#
# **왜**: 영화 글 744편을 아카이브로 옮긴 뒤 남은 글이 98편인데, 태그는 254개다.
# 그중 172개(68%)가 **1편짜리**, 223개(88%)가 2편 이하다. 사이트맵 369 URL 중
# 255개가 태그 페이지이고 대부분 내용이 없다.
#
# 이 상태는 "글 98편 + 거의 빈 페이지 223개"로 보인다. 같은 패턴이
# starnopsis.com 에서 GSC `발견됨-미색인` 6,736건을 만들었다 — 크롤 예산을
# 한 편짜리 복제 페이지에 쓰게 만들고, 사이트 전체 품질 신호를 끌어내린다.
# 애드센스가 2026-09-10 에 이 블로그를 `가치가 별로 없는 콘텐츠`로 거절한
# 맥락에서 그냥 둘 수 없다.
#
# **무엇을 하나**: `jekyll-archives` 가 만든 아카이브 페이지 중 글이
# `MIN_POSTS` 미만인 것에
#   · `sitemap: false`  → jekyll-sitemap 이 사이트맵에서 뺀다
#   · `noindex: true`   → `_includes/head.html` 이 robots 메타를 넣는다
# 를 붙인다. **페이지 자체는 그대로 살아 있다** — 사람이 링크를 타고 오면
# 정상적으로 보인다. 색인 요청만 하지 않는 것이다.
#
# **왜 생성기가 아니라 훅인가**: 아카이브 페이지는 `jekyll-archives` 의
# Generator 가 만든다. 그래서 `:site, :post_read` 시점엔 아직 존재하지 않고,
# 제너레이터가 모두 돈 뒤인 `:site, :pre_render` 에서 잡아야 한다.
#
# 되돌리려면 이 파일을 지우면 된다(그리고 head.html 의 noindex 두 줄).

module ThinArchive
  # 3편 미만을 얇다고 본다. MovieSpoiler 의 `MIN_MOVIES_FOR_INDEX` 와 같은 값 —
  # 두 사이트가 같은 기준을 쓰는 편이 나중에 판단하기 쉽다.
  MIN_POSTS = 3
end

Jekyll::Hooks.register :site, :pre_render do |site|
  thin = 0
  kept = 0

  site.pages.each do |page|
    # jekyll-archives 가 만든 페이지만 대상. 일반 페이지(about, tabs 등)는
    # `page.data['posts']` 가 없으므로 자연히 걸러진다.
    posts = page.data['posts']
    next unless posts.is_a?(Array)

    if posts.size < ThinArchive::MIN_POSTS
      page.data['sitemap'] = false
      page.data['noindex'] = true
      thin += 1
    else
      kept += 1
    end
  end

  Jekyll.logger.info 'ThinArchive:',
                     "얇은 아카이브 #{thin}개 noindex+사이트맵 제외, #{kept}개 유지 " \
                     "(기준: 글 #{ThinArchive::MIN_POSTS}편 미만)"
end
