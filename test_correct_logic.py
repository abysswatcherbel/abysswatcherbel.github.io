from datetime import datetime, timezone
from util.seasonal_schedule import SeasonScheduler

# Teste para entender a lógica correta:
# Episode schedule: domingo a quinta (episódios são exibidos)
# Post schedule: posts de ranking aos domingos 13:00 UTC (10:00 -03:00)

print("=== TESTANDO A LÓGICA ATUAL ===")
print("Data atual: Sábado, 28 de junho de 2025")
print()

# Teste de hoje (sábado 28/06/2025)
today = datetime(2025, 6, 28, 15, 0, 0, tzinfo=timezone.utc)  # 3 PM UTC
print(f"Testando: {today} (Sábado)")

episodes_scheduler = SeasonScheduler(schedule_type='episodes', post_time=today)
post_scheduler = SeasonScheduler(schedule_type='post', post_time=today)

print(f"Episodes Schedule: Season {episodes_scheduler.season_number} ({episodes_scheduler.season_name}), Week {episodes_scheduler.week_id}")
print(f"Post Schedule:     Season {post_scheduler.season_number} ({post_scheduler.season_name}), Week {post_scheduler.week_id}")
print()

print("EXPECTATIVA:")
print("Episodes Schedule: Season 3 (summer), Week 1  # porque já passou quinta-feira")
print("Post Schedule:     Season 2 (spring), Week 13 # porque ainda não chegou domingo 13:00 UTC")
print()

# Vamos verificar alguns pontos de transição críticos
test_dates = [
    # Quinta-feira 26/06 - último dia da semana de episódios
    datetime(2025, 6, 26, 23, 59, 59, tzinfo=timezone.utc),
    # Sexta-feira 27/06 - primeiro dia da nova semana de episódios
    datetime(2025, 6, 27, 0, 0, 0, tzinfo=timezone.utc),
    # Sábado 28/06 (hoje)
    datetime(2025, 6, 28, 15, 0, 0, tzinfo=timezone.utc),
    # Domingo 29/06 12:59 UTC - antes do post
    datetime(2025, 6, 29, 12, 59, 59, tzinfo=timezone.utc),
    # Domingo 29/06 13:00 UTC - momento do post
    datetime(2025, 6, 29, 13, 0, 0, tzinfo=timezone.utc),
    # Domingo 29/06 13:01 UTC - após o post
    datetime(2025, 6, 29, 13, 1, 0, tzinfo=timezone.utc),
]

print("=== PONTOS DE TRANSIÇÃO CRÍTICOS ===")
for test_date in test_dates:
    day_name = test_date.strftime('%A')
    print(f"\n{day_name} {test_date.strftime('%Y-%m-%d %H:%M:%S UTC')}:")
    
    episodes = SeasonScheduler(schedule_type='episodes', post_time=test_date)
    posts = SeasonScheduler(schedule_type='post', post_time=test_date)
    
    print(f"  Episodes: Season {episodes.season_number}, Week {episodes.week_id}")
    print(f"  Posts:    Season {posts.season_number}, Week {posts.week_id}")

print("\n=== ANÁLISE DOS CSVs ===")
import pandas as pd

# Verificar episodes.csv
episodes_df = pd.read_csv('src/season_references/2025/episodes.csv')
episodes_df["start_date"] = pd.to_datetime(episodes_df["start_date"], utc=True)
episodes_df["end_date"] = pd.to_datetime(episodes_df["end_date"], utc=True)

print("\nÚltima semana da primavera (episodes):")
spring_last = episodes_df[(episodes_df['season'] == 2) & (episodes_df['week_id'] == 13)]
if not spring_last.empty:
    row = spring_last.iloc[0]
    print(f"Season 2, Week 13: {row['start_date']} a {row['end_date']}")

print("\nPrimeira semana do verão (episodes):")
summer_first = episodes_df[(episodes_df['season'] == 3) & (episodes_df['week_id'] == 1)]
if not summer_first.empty:
    row = summer_first.iloc[0]
    print(f"Season 3, Week 1: {row['start_date']} a {row['end_date']}")

# Verificar post.csv
post_df = pd.read_csv('src/season_references/2025/post.csv')
post_df["start_date"] = pd.to_datetime(post_df["start_date"], utc=True)
post_df["end_date"] = pd.to_datetime(post_df["end_date"], utc=True)

print("\nÚltima semana da primavera (posts):")
spring_last_post = post_df[(post_df['season'] == 2) & (post_df['week_id'] == 13)]
if not spring_last_post.empty:
    row = spring_last_post.iloc[0]
    print(f"Season 2, Week 13: {row['start_date']} a {row['end_date']}")

print("\nPrimeira semana do verão (posts):")
summer_first_post = post_df[(post_df['season'] == 3) & (post_df['week_id'] == 1)]
if not summer_first_post.empty:
    row = summer_first_post.iloc[0]
    print(f"Season 3, Week 1: {row['start_date']} a {row['end_date']}")
