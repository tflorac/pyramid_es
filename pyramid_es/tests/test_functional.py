from unittest import TestCase

import pyes

from ..client import ElasticClient

from .data import Base, Genre, Movie, get_data


class TestClient(TestCase):

    def setUp(self):
        self.client = ElasticClient(servers=['localhost:9200'],
                                    index='pyramid_es_tests')

    def test_ensure_index(self):
        # First ensure it with no args.
        self.client.ensure_index()

        # Recreate.
        self.client.ensure_index(recreate=True)

        # Delete explicitly.
        self.client.es.delete_index(self.client.index)

        # One more time.
        self.client.ensure_index(recreate=True)

    def test_ensure_mapping_recreate(self):
        # First create.
        self.client.ensure_mapping(Movie)

        # Recreate.
        self.client.ensure_mapping(Movie, recreate=True)

        # Explicitly delete.
        self.client.es.delete_mapping(self.client.index, 'Movie')

        # One more time.
        self.client.ensure_mapping(Movie, recreate=True)

    def test_ensure_all_mappings(self):
        self.client.ensure_all_mappings(Base)

    def test_get_mappings(self):
        mapping = self.client.get_mappings(Movie)
        mapping = mapping['Movie']
        self.assertEqual(mapping['properties']['title'],
                         {'type': 'string', 'boost': 5.0})

    def test_disable_indexing(self):
        self.client.disable_indexing = True
        movie = Movie(title=u'Die Hard',
                      director=u'John McTiernan',
                      year=1988,
                      rating=8.3)
        self.client.index_object(movie)

        num = self.client.query(Movie, q='mctiernan').count()
        self.assertEqual(num, 0)


class TestQuery(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = ElasticClient(servers=['localhost:9200'],
                                   index='pyramid_es_tests')
        cls.client.ensure_index(recreate=True)
        cls.client.ensure_mapping(Movie)

        cls.genres, cls.movies = get_data()

        cls.client.index_objects(cls.genres)
        cls.client.index_objects(cls.movies)
        cls.client.refresh()

    def test_query_all(self):
        result = self.client.query(Movie).execute()
        self.assertEqual(result.count, 8)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn(u'Metropolis', titles)

    def test_sorted(self):
        result = self.client.query(Movie).order_by('year', desc=True).execute()
        self.assertEqual(result.count, 8)

        records = list(result)
        self.assertEqual(records[0].title, u'Annie Hall')
        self.assertEqual(records[0]._score, None)

    def test_filter_year_lower(self):
        q = self.client.query(Movie)
        # Movies made after 1960.
        q = q.filter_value_lower('year', 1960)
        result = q.execute()
        self.assertEqual(result.count, 2)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertItemsEqual([u'Sleeper', u'Annie Hall'], titles)

    def test_filter_rating_upper(self):
        q = self.client.query(Movie)
        q = q.filter_value_upper('rating', 7.5)
        result = q.execute()
        self.assertEqual(result.count, 3)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn(u'Destination Tokyo', titles)

    def test_keyword(self):
        q = self.client.query(Movie, q='hitchcock')
        result = q.execute()
        self.assertEqual(result.count, 3)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn(u'To Catch a Thief', titles)

    def test_filter_term_int(self):
        q = self.client.query(Movie).\
            filter_term('year', 1927)
        result = q.execute()
        self.assertEqual(result.count, 1)

        records = list(result)
        titles = [rec.title for rec in records]
        self.assertIn(u'Metropolis', titles)

    def test_limit(self):
        q = self.client.query(Movie).order_by('year').limit(3)
        result = q.execute()
        self.assertEqual(result.count, 8)

        records = list(result)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].title, u'Metropolis')

    def test_offset(self):
        q = self.client.query(Movie).order_by('year').offset(4)
        result = q.execute()
        self.assertEqual(result.count, 8)

        records = list(result)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].title, u'Vertigo')

    def test_limit_twice(self):
        q = self.client.query(Movie).order_by('year').limit(3)
        with self.assertRaises(ValueError):
            q.limit(5)

    def test_offset_twice(self):
        q = self.client.query(Movie).order_by('year').offset(4)
        with self.assertRaises(ValueError):
            q.offset(7)

    def test_count(self):
        q = self.client.query(Movie)
        self.assertEqual(q.count(), 8)

    def test_raw_query(self):
        raw_query = pyes.MatchAllQuery()
        q = self.client.query(Movie, q=raw_query)
        result = q.execute()
        self.assertEqual(result.count, 8)

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