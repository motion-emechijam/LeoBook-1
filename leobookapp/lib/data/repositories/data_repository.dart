import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:csv/csv.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/constants/api_urls.dart';
import '../models/match_model.dart';
import '../models/recommendation_model.dart';
import 'dart:convert';

class DataRepository {
  static const String _keyPredictions = 'cached_predictions';
  static const String _keyRecommended = 'cached_recommended';

  Future<List<MatchModel>> fetchMatches() async {
    final prefs = await SharedPreferences.getInstance();

    try {
      // 1. Fetch predictions.csv only (schedules.csv not needed per user requirements)
      // Extended timeout to 180s due to 6.8 MB file size
      final predictionsResponse = await http
          .get(Uri.parse(ApiUrls.predictions))
          .timeout(const Duration(seconds: 180));

      String? predictionsBody;

      if (predictionsResponse.statusCode == 200) {
        predictionsBody = predictionsResponse.body;
        await prefs.setString(_keyPredictions, predictionsBody);
      } else {
        // Fallback to cache if fetch failed
        predictionsBody = prefs.getString(_keyPredictions);
      }

      if (predictionsBody == null) return [];

      // 2. Process Predictions CSV
      List<List<dynamic>> pRows = const CsvToListConverter().convert(
        predictionsBody,
        eol: '\n',
      );

      if (pRows.isEmpty) return [];

      final pHeaders = pRows.first.map((e) => e.toString()).toList();
      final pData = pRows.skip(1).toList();

      return pData
          .where((row) => row.length >= pHeaders.length)
          .map((row) {
            final map = Map<String, dynamic>.fromIterables(pHeaders, row);
            return MatchModel.fromCsv(
              map,
              map,
            ); // predictions data is in the same row
          })
          .where((m) => m.prediction != null && m.prediction!.isNotEmpty)
          .toList();
    } catch (e) {
      debugPrint("DataRepository Error (Fetching/Cache): $e");
      // Final fallback to cache
      final cachedPredictions = prefs.getString(_keyPredictions);
      if (cachedPredictions != null) {
        return _processSchedulesInternal(cachedPredictions, cachedPredictions);
      }
      return [];
    }
  }

  Future<List<RecommendationModel>> fetchRecommendations() async {
    final prefs = await SharedPreferences.getInstance();
    try {
      final response = await http
          .get(Uri.parse(ApiUrls.recommended))
          .timeout(const Duration(seconds: 30));

      String? body;
      if (response.statusCode == 200) {
        body = utf8.decode(response.bodyBytes);
        await prefs.setString(_keyRecommended, body);
      } else {
        body = prefs.getString(_keyRecommended);
      }

      if (body == null) return [];

      final List<dynamic> jsonList = jsonDecode(body);
      return jsonList
          .map((json) => RecommendationModel.fromJson(json))
          .toList();
    } catch (e) {
      debugPrint("Error fetching recommendations: $e");
      final cached = prefs.getString(_keyRecommended);
      if (cached != null) {
        final List<dynamic> jsonList = jsonDecode(cached);
        return jsonList
            .map((json) => RecommendationModel.fromJson(json))
            .toList();
      }
      return [];
    }
  }

  List<MatchModel> _processSchedulesInternal(
    String schedulesBody,
    String? predictionsBody,
  ) {
    Map<String, Map<String, dynamic>> predictionsMap = {};
    if (predictionsBody != null) {
      try {
        List<List<dynamic>> pRows = const CsvToListConverter().convert(
          predictionsBody,
          eol: '\n',
        );
        if (pRows.isNotEmpty) {
          final pHeaders = pRows.first.map((e) => e.toString()).toList();
          final pData = pRows.skip(1).toList();
          for (var row in pData) {
            if (row.length >= pHeaders.length) {
              final map = Map<String, dynamic>.fromIterables(pHeaders, row);
              final fid = map['fixture_id']?.toString();
              if (fid != null) predictionsMap[fid] = map;
            }
          }
        }
      } catch (e) {
        /* ignore */
      }
    }

    try {
      List<List<dynamic>> rows = const CsvToListConverter().convert(
        schedulesBody,
        eol: '\n',
      );
      if (rows.isEmpty) return [];
      final headers = rows.first.map((e) => e.toString()).toList();
      final data = rows.skip(1).toList();

      return data
          .where((row) => row.length >= headers.length)
          .map((row) {
            final map = Map<String, dynamic>.fromIterables(headers, row);
            return MatchModel.fromCsv(
              map,
              predictionsMap[map['fixture_id']?.toString()],
            );
          })
          .where((m) => m.prediction != null && m.prediction!.isNotEmpty)
          .toList();
    } catch (e) {
      return [];
    }
  }
}
