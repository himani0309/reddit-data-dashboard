# streamlit_dashboard.py

import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📊 Reddit Digital Currency Dashboard")

# Load CSV
df = pd.read_csv("output_filtered.csv")
df['post_date'] = pd.to_datetime(df['post_date'], errors='coerce')
df['post_month'] = df['post_date'].dt.to_period('M')

# ---- Plot 1: Post Upvotes Over Time ----
st.subheader("1. 📈 Post Upvotes Over Time")
fig1, ax1 = plt.subplots()
df.groupby('post_month')['post_upvotes'].sum().plot(ax=ax1, marker='o')
ax1.set_ylabel("Total Upvotes")
ax1.set_xlabel("Month")
st.pyplot(fig1)

# ---- Plot 2: Total Comments Over Time ----
st.subheader("2. 💬 Total Comments Over Time")
fig2, ax2 = plt.subplots()
df.groupby('post_month')['total_comments'].sum().plot(ax=ax2, marker='s', color='teal')
ax2.set_ylabel("Total Comments")
st.pyplot(fig2)

# ---- Plot 3: Average Upvotes per Post ----
st.subheader("3. 📊 Average Upvotes per Post (Monthly)")
fig3, ax3 = plt.subplots()
df.groupby('post_month')['post_upvotes'].mean().plot(ax=ax3, marker='D', color='orange')
ax3.set_ylabel("Average Upvotes")
st.pyplot(fig3)

# ---- Plot 4: Comment Density per Post ----
st.subheader("4. 🧮 Comment Density (Comments per Upvote)")
df['comment_density'] = df['total_comments'] / (df['post_upvotes'] + 1)
fig4, ax4 = plt.subplots()
sns.histplot(df['comment_density'], bins=30, ax=ax4, color='purple')
ax4.set_xlabel("Comment Density")
st.pyplot(fig4)

# ---- Plot 5: Top 10 Most Commented Posts ----
st.subheader("5. 🥇 Top 10 Most Commented Posts")
top_commented = df.sort_values(by='total_comments', ascending=False).head(10)
fig5, ax5 = plt.subplots()
sns.barplot(x='total_comments', y='post_summary', data=top_commented, ax=ax5)
ax5.set_xlabel("Total Comments")
ax5.set_ylabel("Post Summary")
st.pyplot(fig5)

# ---- Plot 6: Word Cloud of Post Summaries ----
st.subheader("6. ☁️ Word Cloud of Post Summaries")
all_text = " ".join(df['post_summary'].dropna().astype(str).tolist())
wordcloud = WordCloud(width=800, height=400, background_color='white').generate(all_text)
fig6, ax6 = plt.subplots(figsize=(10, 5))
ax6.imshow(wordcloud, interpolation='bilinear')
ax6.axis('off')
st.pyplot(fig6)

# ---- Plot 7: Top Words in Comments ----
st.subheader("7. 📝 Top Words in Comments")
comment_cols = [f'comment_{i}_summary' for i in range(1, 6)]
all_comments = df[comment_cols].fillna("").apply(lambda x: " ".join(x), axis=1)
comment_wordcloud = WordCloud(width=800, height=400, background_color='black').generate(" ".join(all_comments))
fig7, ax7 = plt.subplots(figsize=(10, 5))
ax7.imshow(comment_wordcloud, interpolation='bilinear')
ax7.axis('off')
st.pyplot(fig7)

# ---- Plot 8: Post Length Distribution ----
st.subheader("8. 📏 Distribution of Post Summary Length")
df['post_length'] = df['post_summary'].astype(str).apply(len)
fig8, ax8 = plt.subplots()
sns.histplot(df['post_length'], bins=30, ax=ax8, color='brown')
st.pyplot(fig8)

# ---- Plot 9: Misinformation Mentions Over Time ----
st.subheader("9. ❗ Misinformation Mentions Over Time")
mis_keywords = ['fake', 'misinformation', 'wrong', 'false']
df['mis_flag'] = df['post_summary'].fillna("").str.lower().apply(lambda x: any(k in x for k in mis_keywords))
mis_monthly = df[df['mis_flag']].groupby('post_month').size()
fig9, ax9 = plt.subplots()
mis_monthly.plot(ax=ax9, marker='x', color='red')
ax9.set_title("Mentions of Misinformation Terms")
st.pyplot(fig9)

# ---- Plot 10: Theme Overlap (Post vs Comments) ----
st.subheader("10. 🎭 Theme Overlap (Post vs Comments)")
themes = ['positive', 'negative', 'neutral']
comment_summary = df[comment_cols].fillna("").agg(lambda row: " ".join(row), axis=1)
theme_match = df['post_summary'].str.lower().str.extract(f"({'|'.join(themes)})")[0] == comment_summary.str.lower().str.extract(f"({'|'.join(themes)})")[0]
alignment_df = pd.Series(theme_match).value_counts(normalize=True) * 100
fig10, ax10 = plt.subplots()
alignment_df.plot(kind='bar', ax=ax10, color=['green', 'red'])
ax10.set_xticklabels(['Matched', 'Not Matched'], rotation=0)
ax10.set_ylabel("Percentage")
st.pyplot(fig10)

# ---- Plot 11: Comment Sentiment Count ----
st.subheader("11. 🧠 Comment Sentiment Count")
sentiment_terms = ['fake', 'misinfo', 'truth', 'neutral']
comment_all_text = all_comments.str.lower()
sentiment_counts = {term: comment_all_text.str.contains(term).sum() for term in sentiment_terms}
fig11, ax11 = plt.subplots()
pd.Series(sentiment_counts).plot(kind='bar', ax=ax11, color='steelblue')
st.pyplot(fig11)

# ---- Plot 12: Monthly Theme Trend ----
st.subheader("12. 📅 Monthly Theme (Keyword Based)")
theme_labels = ['positive', 'negative', 'neutral']
df['theme'] = df['post_summary'].str.lower().apply(lambda x: next((k for k in theme_labels if k in x), 'unknown'))
theme_monthly = df.groupby(['post_month', 'theme']).size().unstack().fillna(0)
fig12, ax12 = plt.subplots()
theme_monthly.plot(ax=ax12)
ax12.set_ylabel("Count")
st.pyplot(fig12)

# ---- Plot 13: Controversial Posts ----
st.subheader("13. 🔥 Top 10 Controversial Posts")
df['controversy_score'] = df['post_upvotes'] + df['total_comments']
top_contro = df.sort_values('controversy_score', ascending=False).head(10)
fig13, ax13 = plt.subplots()
sns.barplot(y='post_summary', x='controversy_score', data=top_contro, ax=ax13, palette='rocket')
st.pyplot(fig13)

