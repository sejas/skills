# AI Radar — Source Buckets

One research agent per bucket. Each agent: WebSearch/WebFetch the sources, return findings from the last ~6 weeks as `item | date | url | one-line what | why notable`. No in-window output → report `source quiet this window`.

Note: X/Twitter handles are search-only proxies — WebFetch can't read x.com; find tweets via WebSearch/news coverage (dates may lag).

## 1. Researchers & builders

- Andrej Karpathy — https://github.com/karpathy , X @karpathy, karpathy.ai (nanoGPT/llm.c lineage, eureka-labs)
- Simon Willison — https://simonwillison.net (LLM tooling, practical evals — highest signal for workflows)
- swyx / Latent Space — https://www.latent.space
- Lilian Weng — https://lilianweng.github.io
- Sebastian Raschka — https://magazine.sebastianraschka.com
- François Chollet — X @fchollet (ARC, program synthesis)
- Chip Huyen — https://huyenchip.com/blog

## 2. Labs

- Anthropic — https://www.anthropic.com/research + engineering blog
- OpenAI — https://openai.com/research
- Google DeepMind — https://deepmind.google/discover/blog
- Meta AI — https://ai.meta.com/blog
- DeepSeek, Qwen, Mistral — release notes / model cards (search "<lab> release" recent)

## 3. Papers & aggregators

- Hugging Face daily papers — https://huggingface.co/papers (best single trending signal)
- arXiv new: cs.CL, cs.LG, cs.AI — search for high-velocity papers, not the full firehose
- alphaXiv trending — https://www.alphaxiv.org

## 4. Repos & community

- GitHub trending — https://github.com/trending (weekly, Python + TypeScript)
- Hacker News — search "AI" front-page stories past month
- smol.ai AI News — https://news.smol.ai (daily digest of X/Discord/Reddit)

## Adding sources

Append here. Keep each bucket ≤8 entries — radar dies of firehose.
