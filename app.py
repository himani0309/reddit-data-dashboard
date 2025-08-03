# streamlit_dashboard.py

import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from wordcloud import WordCloud

st.set_page_config(layout="wide")
st.title("📊 Reddit Digital Currency Dashboard")

# Load CSV
df = pd.read_csv("output/reddit/output_processed.csv")
df['post_date'] = pd.to_datetime(df['post_date'], errors='coerce')
df['post_month'] = df['post_date'].dt.to_period('M')

# Fix column names
df.rename(columns={
    'post_upvotes': 'post_upvote',
    'total_comments': 'post_total_comments'
}, inplace=True)

comment_cols = [f'comment_{i}_summary' for i in range(1, 6)]

# --------------------- PLOTS ---------------------

# 1. Post Upvotes Over Time
st.subheader("1. 📈 Post Upvotes Over Time")
fig1, ax1 = plt.subplots(figsize=(8, 4))
df.groupby('post_month')['post_upvote'].sum().plot(ax=ax1, marker='o')
ax1.set_ylabel("Total Upvotes")
st.pyplot(fig1)

# 2. Total Comments Over Time
st.subheader("2. 💬 Total Comments Over Time")
fig2, ax2 = plt.subplots(figsize=(8, 4))
df.groupby('post_month')['post_total_comments'].sum().plot(ax=ax2, marker='s', color='teal')
ax2.set_ylabel("Total Comments")
st.pyplot(fig2)

# 3. Average Upvotes per Post
st.subheader("3. 📊 Average Upvotes per Post (Monthly)")
fig3, ax3 = plt.subplots(figsize=(8, 4))
df.groupby('post_month')['post_upvote'].mean().plot(ax=ax3, marker='D', color='orange')
ax3.set_ylabel("Average Upvotes")
st.pyplot(fig3)

# 4. Comment Density
st.subheader("4. 🧮 Comment Density (Comments per Upvote)")
df['comment_density'] = df['post_total_comments'] / (df['post_upvote'] + 1)
fig4, ax4 = plt.subplots(figsize=(8, 4))
sns.histplot(df['comment_density'], bins=30, ax=ax4, color='purple')
ax4.set_xlabel("Comment Density")
st.pyplot(fig4)

# 5. Top 10 Most Commented Posts
st.subheader("5. 🥇 Top 10 Most Commented Posts")
top_commented = df.sort_values(by='post_total_comments', ascending=False).head(10)
fig5, ax5 = plt.subplots(figsize=(8, 4))
sns.barplot(x='post_total_comments', y='post_summary', data=top_commented, ax=ax5)
ax5.set_xlabel("Total Comments")
st.pyplot(fig5)

# 6. Word Cloud of Post Summaries
st.subheader("6. ☁️ Word Cloud of Post Summaries")
all_text = " ".join(df['post_summary'].dropna().astype(str).tolist())
wordcloud = WordCloud(width=800, height=400, background_color='white').generate(all_text)
fig6, ax6 = plt.subplots(figsize=(8, 4))
ax6.imshow(wordcloud, interpolation='bilinear')
ax6.axis('off')
st.pyplot(fig6)

# 7. Word Cloud from Comments
st.subheader("7. 📝 Top Words in Comments")
all_comments = df[comment_cols].fillna("").apply(lambda x: " ".join(x), axis=1)
comment_wordcloud = WordCloud(width=800, height=400, background_color='black').generate(" ".join(all_comments))
fig7, ax7 = plt.subplots(figsize=(10, 5))
ax7.imshow(comment_wordcloud, interpolation='bilinear')
ax7.axis('off')
st.pyplot(fig7)

# 8. Distribution of Post Length
st.subheader("8. 📏 Distribution of Post Summary Length")
df['post_length'] = df['post_summary'].astype(str).apply(len)
fig8, ax8 = plt.subplots(figsize=(8, 4))
sns.histplot(df['post_length'], bins=30, ax=ax8, color='brown')
st.pyplot(fig8)

# 9. 🥧 Post Theme Distribution (Keyword Extracted Pie)
st.subheader("9. 🥧 Post Theme Distribution")
theme_labels = ['positive', 'negative', 'neutral']
df['theme'] = df['post_summary'].str.lower().apply(lambda x: next((k for k in theme_labels if k in x), 'unknown'))
fig9, ax9 = plt.subplots(figsize=(6, 6))
df['theme'].value_counts().plot.pie(autopct='%1.1f%%', startangle=140, ax=ax9)
ax9.set_ylabel("")
st.pyplot(fig9)

# 10. Theme Overlap (Post vs Comments)
st.subheader("10. 🎭 Theme Overlap (Post vs Comments)")
comment_summary = df[comment_cols].fillna("").agg(lambda row: " ".join(row), axis=1)
theme_match = df['theme'] == comment_summary.str.lower().str.extract(f"({'|'.join(theme_labels)})")[0]
alignment_df = pd.Series(theme_match).value_counts(normalize=True) * 100
fig10, ax10 = plt.subplots(figsize=(6, 4))
alignment_df.plot(kind='bar', ax=ax10, color=['green', 'red'])
ax10.set_xticklabels(['Matched', 'Not Matched'], rotation=0)
ax10.set_ylabel("Percentage")
st.pyplot(fig10)

# 11. Comment Sentiment Count (Keywords)
st.subheader("11. 🧠 Comment Sentiment Keywords")
sentiment_terms = ['fake', 'misinfo', 'truth', 'neutral']
comment_all_text = all_comments.str.lower()
sentiment_counts = {term: comment_all_text.str.contains(term).sum() for term in sentiment_terms}
fig11, ax11 = plt.subplots(figsize=(8, 4))
pd.Series(sentiment_counts).plot(kind='bar', ax=ax11, color='steelblue')
st.pyplot(fig11)

# 12. Monthly Theme Trends
st.subheader("12. 📅 Monthly Theme Trends")
theme_monthly = df.groupby(['post_month', 'theme']).size().unstack().fillna(0)
fig12, ax12 = plt.subplots(figsize=(8, 4))
theme_monthly.plot(ax=ax12)
ax12.set_ylabel("Number of Posts")
st.pyplot(fig12)

# 13. Top Controversial Posts (Upvotes + Comments)
st.subheader("13. 🔥 Top 10 Controversial Posts")
df['controversy_score'] = df['post_upvote'] + df['post_total_comments']
top_contro = df.sort_values('controversy_score', ascending=False).head(10)
fig13, ax13 = plt.subplots(figsize=(8, 4))
sns.barplot(y='post_summary', x='controversy_score', data=top_contro, ax=ax13, palette='rocket')
st.pyplot(fig13)
