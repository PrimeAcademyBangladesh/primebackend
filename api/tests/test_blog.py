from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from api.models.models_blog import Blog, BlogCategory


class BlogApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # create a category and a blog
        self.category = BlogCategory.objects.create(name="Entre", is_active=True)
        self.blog = Blog.objects.create(
            category=self.category,
            title="Test Blog Title",
            excerpt="Short excerpt",
            content="Full content of the blog post",
            status="published"
        )

    def test_blog_list_returns_paginated_results(self):
        url = reverse('blog-list')
        resp = self.client.get(url, format='json')
        self.assertEqual(resp.status_code, 200)
        # List view uses pagination and uses api_response envelope;
        # expect success/message/data where data contains count/results
        self.assertTrue(resp.data.get('success', False))
        self.assertIn('data', resp.data)
        data = resp.data['data']
        self.assertIn('results', data)
        self.assertEqual(data.get('count', 0), 1)

    def test_blog_detail_returns_enveloped_data(self):
        # URL name changed to 'blog-retrieve-slug' in api/urls.py
        url = reverse('blog-retrieve-slug', kwargs={'slug': self.blog.slug})
        resp = self.client.get(url, format='json')
        self.assertEqual(resp.status_code, 200)
        # Detail view wraps response with api_response: success/message/data
        self.assertTrue(resp.data.get('success', False))
        self.assertIn('data', resp.data)
        data = resp.data['data']
        self.assertEqual(data.get('slug'), self.blog.slug)
        self.assertEqual(data.get('title'), self.blog.title)
