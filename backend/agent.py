import requests
from bs4 import BeautifulSoup
import nltk
import heapq
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
import os
from datetime import datetime

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

class SummarizeAgent:
    def __init__(self):
        pass

    def extract_content(self, url: str) -> tuple[str, str]:
        """
        Extract article content and title from URL.
        Returns: (content, title)
        Raises: ValueError if extraction fails
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Check if this is a journal homepage
        is_journal_homepage = url.lower().endswith('?tab=toc') == False and any(indicator in url.lower() for indicator in ['/journal/', '/journals/', 'springer.com/journal'])
        is_article_page = ('/article/' in url.lower() or '/chapter/' in url.lower() or ('/' in url.lower().split('?')[0].split('#')[0] and url.lower().split('?')[0].split('#')[0].count('/') > 3))

        article_title = soup.title.string if soup.title else "Untitled"

        if is_journal_homepage and not is_article_page:
            raise ValueError("This appears to be a journal homepage, not a specific article. Please provide a direct link to an article instead of the journal's main page.")

        # Improved content extraction strategies
        article_text = self._extract_with_selectors(soup)
        if not article_text.strip():
            article_text = self._extract_from_paragraphs(soup)
        if not article_text.strip():
            article_text = self._extract_from_elements(soup)
        if not article_text.strip():
            article_text = self._extract_from_body(soup)

        if not article_text.strip():
            raise ValueError("Unable to extract article content. The website may not allow automated content extraction.")

        return article_text, article_title

    def _extract_with_selectors(self, soup):
        content_selectors = [
            'article', '[role="main"]', 'main', '.article-content', '.post-content',
            '.entry-content', '.content', '#content', '.article-body', '.post-body'
        ]
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                paragraphs = content_elem.find_all('p')
                article_text = ' '.join([p.get_text() for p in paragraphs])
                if article_text.strip():
                    return article_text
        return ""

    def _extract_from_paragraphs(self, soup):
        paragraphs = soup.find_all('p')
        return ' '.join([p.get_text() for p in paragraphs])

    def _extract_from_elements(self, soup):
        text_elements = soup.find_all(['p', 'div', 'span', 'li'])
        filtered_text = []
        for elem in text_elements:
            text = elem.get_text().strip()
            if len(text) > 20 and not any(skip in text.lower() for skip in [
                'copyright', 'privacy policy', 'terms of service', 'sign up', 'login', 'subscribe'
            ]):
                filtered_text.append(text)
        return ' '.join(filtered_text)

    def _extract_from_body(self, soup):
        body = soup.find('body')
        if not body:
            return ""
        all_text = body.get_text()
        chunks = [chunk.strip() for chunk in all_text.split('\n\n') if chunk.strip()]
        meaningful_chunks = []
        for chunk in chunks:
            if len(chunk) > 30 and not any(skip in chunk.lower() for skip in [
                'copyright', 'privacy policy', 'terms of service', 'sign up', 'login', 'subscribe',
                'cookies', 'accept cookies', 'cookie settings', 'follow us', 'contact us'
            ]):
                meaningful_chunks.append(chunk)
        return ' '.join(meaningful_chunks[:20])  # Limit to prevent huge extraction

    def summarize(self, text: str) -> str:
        """
        Generate extractive summary using NLTK.
        """
        stopWords = set(stopwords.words("english"))
        words = word_tokenize(text)
        freqTable = {word.lower(): 0 for word in words if word.lower() not in stopWords}

        for word in words:
            word = word.lower()
            if word in freqTable:
                freqTable[word] += 1

        if not freqTable:
            return "Unable to summarize: no words found for frequency calculation."

        max_freq = max(freqTable.values())
        for word in freqTable:
            freqTable[word] = freqTable[word] / max_freq

        sentences = sent_tokenize(text)
        sentenceValue = {sentence: 0 for sentence in sentences}

        for sentence in sentences:
            words_in_sentence = word_tokenize(sentence)
            for word in words_in_sentence:
                if word.lower() in freqTable:
                    sentenceValue[sentence] += freqTable[word.lower()]

        if not sentenceValue:
            return "Unable to summarize: no sentences found for ranking."

        sumValues = sum(sentenceValue.values())
        average = sumValues / len(sentenceValue)

        summary_sentences = heapq.nlargest(7, sentenceValue, key=sentenceValue.get)
        return ' '.join(summary_sentences)

    def process(self, url: str) -> tuple[str, str]:
        """
        Main method: extract and summarize.
        Returns: (summary, title)
        """
        content, title = self.extract_content(url)
        summary = self.summarize(content)
        return summary, title
