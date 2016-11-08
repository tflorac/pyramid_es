from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from unittest import TestCase
from pprint import pprint

from elasticsearch.exceptions import NotFoundError

from ..client import ElasticClient

from .data import Base, Genre, Movie, get_data


class TestClient(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = ElasticClient(servers=['localhost:9200'],
                                   index='pyramid_es_tests',
                                   use_transaction=False)
        if cls.client.es.indices.exists(cls.client.index):
            cls.client.delete_index()

    def test_ensure_index(self):
        # First ensure it with no args.
        self.client.ensure_index()

        # Recreate.
        self.client.ensure_index(recreate=True)

        # Delete explicitly.
        self.client.delete_index()

        # One more time.
        self.client.ensure_index(recreate=True)

    def test_ensure_mapping_recreate(self):
        # First create.
        self.client.ensure_mapping(Movie)

        # Recreate.
        self.client.ensure_mapping(Movie, recreate=True)

        # Explicitly delete.
        self.client.delete_mapping(Movie)

        # One more time.
        self.client.ensure_mapping(Movie, recreate=True)

    def test_ensure_all_mappings(self):
        self.client.ensure_index(recreate=True)
        self.client.ensure_all_mappings(Base)

    def test_get_mappings(self):
        mapping = self.client.get_mappings(Movie)
        self.assertIn('Movie', mapping)
        mapping = mapping['Movie']
        self.assertEqual(mapping['properties']['title'],
                         {'type': 'string', 'boost': 5.0})

    def test_disable_indexing(self):
        self.client.ensure_index(recreate=True)

        self.client.disable_indexing = True
        genre = Genre(title=u'Procedural Electronica')
        self.client.index_object(genre)

        num = self.client.query(Genre, q='Electronica').count()
        self.assertEqual(num, 0)

        self.client.delete_object(genre)

    def test_index_and_delete_document(self):
        doc = dict(question='What is the ultimate question?')
        doc_type = 'Answer'
        id = 42

        self.client.index_document(id=id,
                                   doc_type=doc_type,
                                   doc=doc)
        self.client.refresh()

        # FIXME Search for this document and make sure it exists.

        self.client.delete_document(id=id,
                                    doc_type=doc_type)
        self.client.refresh()

        # FIXME Search for this document and make sure it DOES NOT exist.

    def test_index_and_delete_object(self):
        genre = Genre(title=u'Sci-Fi Romance')
        self.client.index_object(genre)
        self.client.refresh()

        # FIXME Search for this object and make sure it exists.

        self.client.delete_object(genre)
        self.client.refresh()

        # FIXME Search for this object and make sure it DOES NOT exist.

    def test_index_and_delete_object_with_parent(self):
        thriller = Genre(title=u'Thriller')
        self.client.index_object(thriller)

        movie = Movie(
            title=u'Sneakers',
            director=u'Phil Alden Robinson',
            year=1992,
            rating=7.1,  # What is this crap, IMDB?
            genre=thriller,
            genre_id=thriller.id,
        )
        self.client.index_object(movie)
        self.client.refresh()

        # FIXME Search for this object and make sure it exists.

        self.client.delete_object(movie)
        self.client.refresh()

        # FIXME Search for this object and make sure it DOES NOT exist.

    def test_delete_nonexistent_document(self):
        with self.assertRaises(NotFoundError):
            self.client.delete_document(id=1337,
                                        doc_type='Genre')

    def test_delete_nonexistent_document_safe(self):
        self.client.delete_document(id=888,
                                    doc_type='Genre',
                                    safe=True)

    def test_delete_nonexistent_object(self):
        genre = Genre(title=u'Geriatric Philosophy')
        with self.assertRaises(NotFoundError):
            self.client.delete_object(genre)

    def test_delete_nonexistent_object_safe(self):
        genre = Genre(title=u'Geriatric Philosophy')
        self.client.delete_object(genre, safe=True)


class TestQuery(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = ElasticClient(servers=['localhost:9200'],
                                   index='pyramid_es_tests',
                                   use_transaction=False)
        cls.client.ensure_index(recreate=True)
        cls.client.ensure_mapping(Movie)

        cls.genres, cls.movies = get_data()

        cls.client.index_objects(cls.genres)
        cls.client.index_objects(cls.movies)
        cls.client.refresh()

    def test_query_all(self):
        result = self.client.query(Movie).execute()
        self.assertEqual(result.total, 8)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn(u'Metropolis', titles)

    def test_sorted(self):
        result = self.client.query(Movie).order_by('year', desc=True).execute()
        self.assertEqual(result.total, 8)

        records = list(result)
        self.assertEqual(records[0].title, u'Annie Hall')
        self.assertEqual(records[0]._score, None)

    def test_keyword(self):
        q = self.client.query(Movie, q='hitchcock')
        result = q.execute()
        self.assertEqual(result.total, 3)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn(u'To Catch a Thief', titles)

    def test_filter_year_lower(self):
        q = self.client.query(Movie)
        # Movies made after 1960.
        q = q.filter_value_lower('year', 1960)
        result = q.execute()
        self.assertEqual(result.total, 2)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertEqual([u'Annie Hall', u'Sleeper'], sorted(titles))

    def test_filter_rating_upper(self):
        q = self.client.query(Movie)
        q = q.filter_value_upper('rating', 7.5)
        result = q.execute()
        self.assertEqual(result.total, 3)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn(u'Destination Tokyo', titles)

    def test_filter_term_int(self):
        q = self.client.query(Movie).\
            filter_term('year', 1927)
        result = q.execute()
        self.assertEqual(result.total, 1)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn(u'Metropolis', titles)

    def test_filter_terms_int(self):
        q = self.client.query(Movie).\
            filter_terms('year', [1927, 1958])
        result = q.execute()
        self.assertEqual(result.total, 2)

        records = list(result)
        titles = set(rec.title for rec in records)
        self.assertEqual(set([u'Metropolis', u'Vertigo']), titles)

    def test_offset(self):
        q = self.client.query(Movie).order_by('year').offset(4)
        result = q.execute()
        self.assertEqual(result.total, 8)

        records = list(result)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].title, u'Vertigo')

    def test_offset_with_start(self):
        # If you apply .execute(start=N) on a query that already has limit M,
        # the 'start position' actually used should be M+N.
        q = self.client.query(Movie).order_by('year').offset(2)
        result = q.execute(start=2)
        # XXX How should this behave?
        self.assertEqual(result.total, 8)

        records = list(result)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].title, u'Vertigo')

    def test_offset_twice(self):
        q = self.client.query(Movie).order_by('year').offset(4)
        with self.assertRaises(ValueError):
            q.offset(7)

    def test_limit(self):
        q = self.client.query(Movie).order_by('year').limit(3)
        result = q.execute()
        self.assertEqual(result.total, 8)

        records = list(result)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].title, u'Metropolis')

    def test_limit_with_size(self):
        q = self.client.query(Movie).order_by('year').limit(6)
        result = q.execute(size=3)
        # XXX How should this behave?
        self.assertEqual(result.total, 8)

        records = list(result)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].title, u'Metropolis')

    def test_limit_twice(self):
        q = self.client.query(Movie).order_by('year').limit(3)
        with self.assertRaises(ValueError):
            q.limit(5)

    def test_count(self):
        q = self.client.query(Movie)
        self.assertEqual(q.count(), 8)

    def test_get_tuple(self):
        genre = Genre(title=u'Mystery')
        record = self.client.get(('Genre', genre.id))
        self.assertEqual(record.title, u'Mystery')

    def test_get_object(self):
        genre = Genre(title=u'Mystery')
        record = self.client.get(genre)
        self.assertEqual(record.title, u'Mystery')

    def test_get_tuple_with_parent(self):
        genre = Genre(title=u'Mystery')
        movie = Movie(title=u'Vertigo', genre_id=genre.id)
        record = self.client.get(('Movie', movie.id), routing=genre.id)
        self.assertEqual(record.title, u'Vertigo')

    def test_get_object_with_parent(self):
        genre = Genre(title=u'Mystery')
        movie = Movie(title=u'Vertigo', genre_id=genre.id)
        record = self.client.get(movie)
        self.assertEqual(record.title, u'Vertigo')

    def test_add_range_facet(self):
        q = self.client.query(Movie).\
            add_range_facet(name='era_hist',
                            field='year',
                            ranges=[{"to": 1950},
                                    {"from": 1950, "to": 1970},
                                    {"from": 1970, "to": 1990},
                                    {"from": 1990}])

        result = q.execute()
        facets = result.facets
        self.assertEqual(list(facets.keys()), ['era_hist'])
        histogram = facets['era_hist']

        self.assertEqual(histogram['_type'], 'range')

        ranges = histogram['ranges']
        self.assertEqual(len(ranges), 4)
        self.assertEqual(ranges[1]['from'], 1950)
        self.assertEqual(ranges[1]['to'], 1970)
        self.assertEqual(ranges[1]['count'], 3)

    def test_add_term_facet(self):
        q = self.client.query(Movie).\
            add_term_facet(name='genre_hist',
                           field='genre_title',
                           size=3)

        result = q.execute()
        facets = result.facets
        self.assertEqual(list(facets.keys()), ['genre_hist'])
        histogram = facets['genre_hist']

        self.assertEqual(histogram['_type'], 'terms')

        pprint(histogram)
        terms = histogram['terms']
        self.assertEqual(len(terms), 3)
        self.assertEqual(terms[0]['count'], 3)
        self.assertEqual(terms[0]['term'], 'mystery')

    def test_add_term_aggregate(self):
        q = self.client.query(Movie).\
            add_term_aggregate(name='genre_hist',
                               field='genre_title')

        result = q.execute()
        aggregations = result.aggregations
        self.assertEqual(list(aggregations.keys()), ['genre_hist'])
        buckets = aggregations['buckets']

        pprint(buckets)
        self.assertEqual(len(buckets), 3)

    def test_raw_query(self):
        raw_query = {'match_all': {}}
        q = self.client.query(Movie, q=raw_query)
        result = q.execute()
        self.assertEqual(result.total, 8)

    def test_query_fields(self):
        q = self.client.query(Movie, q='hitchcock')
        result = q.execute(fields=['title'])
        self.assertEqual(result.total, 3)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn([u'To Catch a Thief'], titles)

    def test_query_filter_has_parent_term(self):
        q = self.client.query(Movie).\
            filter_has_parent_term('Genre', 'title', 'action')

        result = q.execute()
        self.assertEqual(result.total, 2)
        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn(u'Destination Tokyo', titles)
        self.assertIn(u'Captain Blood', titles)

    def test_add_term_suggester(self):
        q = self.client.query(Movie).\
            add_term_suggester('suggest1',
                               field='title',
                               text='vrtigo')

        result = q.execute()
        self.assertIn('suggest1', result.suggests)
        suggest = result.suggests['suggest1']
        options = suggest[0].get('options')
        self.assertGreater(len(options), 0)
        self.assertEqual(options[0]['text'], 'vertigo')
